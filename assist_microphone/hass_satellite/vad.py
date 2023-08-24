from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

import numpy as np
import onnxruntime
import webrtcvad

_RATE = 16000


class VoiceActivityDetector(ABC):
    @abstractmethod
    def __call__(self, audio: bytes) -> float:
        pass

    def reset(self) -> None:
        pass


class SileroVoiceActivityDetector(VoiceActivityDetector):
    """Detects speech/silence using Silero VAD.

    https://github.com/snakers4/silero-vad
    """

    def __init__(self, onnx_path: Union[str, Path]):
        onnx_path = str(onnx_path)

        self.session = onnxruntime.InferenceSession(onnx_path)
        self.session.intra_op_num_threads = 1
        self.session.inter_op_num_threads = 1

        self._h = np.zeros((2, 1, 64)).astype("float32")
        self._c = np.zeros((2, 1, 64)).astype("float32")

    def reset(self) -> None:
        self._h = np.zeros((2, 1, 64)).astype("float32")
        self._c = np.zeros((2, 1, 64)).astype("float32")

    def __call__(self, audio: bytes):
        """Return probability of speech in audio [0-1].

        Audio must be 16Khz 16-bit mono PCM.
        """
        audio_array = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32767.0

        if len(audio_array.shape) == 1:
            # Add batch dimension
            audio_array = np.expand_dims(audio_array, 0)

        ort_inputs = {
            "input": audio_array.astype(np.float32),
            "h": self._h,
            "c": self._c,
            "sr": np.array(_RATE, dtype=np.int64),
        }
        ort_outs = self.session.run(None, ort_inputs)
        out, self._h, self._c = ort_outs

        return out.squeeze()


class WebrtcVoiceActivityDetector(VoiceActivityDetector):
    def __init__(self, mode: int = 3):
        self.vad = webrtcvad.Vad()
        self.vad.set_mode(mode)

    def __call__(self, audio: bytes) -> float:
        return 1.0 if self.vad.is_speech(audio, _RATE) else 0.0