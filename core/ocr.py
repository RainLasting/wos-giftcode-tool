import json
import io
import os
import time
import base64
import numpy as np
from PIL import Image

try:
    import onnxruntime as ort
    ONNX_AVAILABLE = True
except ImportError:
    ort = None
    ONNX_AVAILABLE = False

EXPECTED_CAPTCHA_LENGTH = 4
VALID_CHARACTERS = set('123456789ABCDEFGHIJKLMNPQRSTUVWXYZ')
OCR_MAX_RETRIES = 2
OCR_RETRY_DELAY_MIN = 0.5
OCR_RETRY_DELAY_MAX = 1.0


class CaptchaSolver:
    def __init__(self, model_path, metadata_path, app_path, log_callback=None):
        self.model_path = model_path
        self.metadata_path = metadata_path
        self.app_path = app_path
        self.log_callback = log_callback
        self.session = None
        self.metadata = None
        self._gpu_enabled = True
        self._init_model()

    def _get_model_path(self, filename):
        import sys
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            local_path = os.path.join(exe_dir, 'model', filename)
            if os.path.exists(local_path):
                return local_path
            return os.path.join(sys._MEIPASS, 'model', filename)
        return os.path.join(self.app_path, 'model', filename)

    def _create_session(self, model_path, providers=None):
        if providers:
            return ort.InferenceSession(model_path, providers=providers)
        return ort.InferenceSession(model_path)

    def _init_model(self):
        if not ONNX_AVAILABLE:
            self._log("ONNX Runtime 未安装", level='warn')
            return

        onnx_model_path = self._get_model_path('captcha_model.onnx')
        onnx_metadata_path = self._get_model_path('captcha_model_metadata.json')
        if not (os.path.exists(onnx_model_path) and os.path.exists(onnx_metadata_path)):
            self._log("ONNX 模型文件未找到", level='warn')
            return

        try:
            providers = None
            if not self._gpu_enabled:
                providers = ['CPUExecutionProvider']

            self.session = self._create_session(onnx_model_path, providers)
            with open(onnx_metadata_path, 'r') as f:
                self.metadata = json.load(f)

            height, width = self.metadata['input_shape'][1:3]
            dummy_img = np.random.rand(1, 1, height, width).astype(np.float32)
            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: dummy_img})

            if len(outputs) == 4:
                accuracy = self.metadata.get('best_accuracy', 0)
                active_providers = self.session.get_providers()
                gpu_info = ""
                for p in active_providers:
                    if p != 'CPUExecutionProvider':
                        gpu_info = f"，加速: {p}"
                        break
                self._log(f"ONNX 模型加载成功（训练精度: {accuracy:.2f}%{gpu_info}）")
            else:
                self._log(f"ONNX 模型测试失败，期望 4 个输出，实际 {len(outputs)} 个", level='error')
                self.session = None
                self.metadata = None
        except Exception as e:
            self._log(f"ONNX 模型初始化失败: {e}", level='error')
            self.session = None
            self.metadata = None

        if not self.session:
            self._log("严重错误：ONNX 模型加载失败，OCR 不可用！", level='error')

    def set_gpu_enabled(self, enabled):
        if not ONNX_AVAILABLE or not self.session:
            return

        if enabled == self._gpu_enabled:
            return

        self._gpu_enabled = enabled
        onnx_model_path = self._get_model_path('captcha_model.onnx')
        if not os.path.exists(onnx_model_path):
            return

        try:
            providers = None
            if not enabled:
                providers = ['CPUExecutionProvider']

            new_session = self._create_session(onnx_model_path, providers)
            new_session.run(None, {new_session.get_inputs()[0].name:
                                   np.random.rand(1, 1, *self.metadata['input_shape'][1:3]).astype(np.float32)})

            self.session = new_session
            active_providers = new_session.get_providers()
            if enabled and any(p != 'CPUExecutionProvider' for p in active_providers):
                self._log(f"GPU 加速已启用（{[p for p in active_providers if p != 'CPUExecutionProvider'][0]}）")
            elif enabled:
                self._log("GPU 加速不可用，将使用 CPU", level='warn')
            else:
                self._log("已切换到 CPU 模式")
        except Exception as e:
            self._log(f"GPU 切换失败，保持当前配置: {e}", level='warn')
            self._gpu_enabled = not enabled

    def _validate_result(self, text):
        if not text or not isinstance(text, str):
            return False
        if len(text) != EXPECTED_CAPTCHA_LENGTH:
            return False
        if not all(c in VALID_CHARACTERS for c in text):
            return False
        if len(set(text)) == 1:
            return False
        return True

    def _parse_captcha_base64(self, img_field):
        if isinstance(img_field, str) and img_field.startswith("data:image"):
            try:
                return img_field.split(",", 1)[1]
            except IndexError:
                return None
        elif isinstance(img_field, str):
            return img_field
        return None

    def solve(self, image_bytes):
        if not self.session or not self.metadata:
            return None

        ocr_start = time.time()
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if image.mode != 'L':
                image = image.convert('L')

            height, width = self.metadata['input_shape'][1:3]
            image = image.resize((width, height), Image.LANCZOS)

            image_array = np.array(image, dtype=np.float32)
            mean = self.metadata['normalization']['mean'][0]
            std = self.metadata['normalization']['std'][0]
            image_array = (image_array / 255.0 - mean) / std
            image_array = np.expand_dims(image_array, axis=(0, 1))

            input_name = self.session.get_inputs()[0].name
            outputs = self.session.run(None, {input_name: image_array})

            idx_to_char = self.metadata['idx_to_char']
            valid_chars = set(self.metadata['chars'])
            predicted_text = ""

            for pos in range(4):
                char_probs = outputs[pos][0]
                predicted_idx = np.argmax(char_probs)
                predicted_text += idx_to_char[str(predicted_idx)]

            if self._validate_result(predicted_text) and all(c in valid_chars for c in predicted_text):
                return predicted_text
            else:
                self._log(f"ONNX 识别结果无效: '{predicted_text}'", level='warn')
                return None
        except Exception as e:
            self._log(f"ONNX 推理错误: {e}", level='error')
            return None

    def _log(self, message, level='info'):
        if self.log_callback:
            self.log_callback(message, level)
