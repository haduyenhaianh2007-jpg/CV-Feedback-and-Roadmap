"""
Local LLM Adapter
Giao tiếp với Qwen2.5-7B-Instruct qua Ollama REST API.

Yêu cầu:
1. Cài Ollama: https://ollama.com/download
2. Pull model: ollama pull qwen2.5:7b-instruct
3. Chạy server: ollama serve (mặc định chạy ở port 11434)

Backend options:
- Ollama (mặc định, đã test với Qwen2.5-7B)
- Có thể mở rộng cho vLLM, llama.cpp server nếu cần
"""
import json
import requests
from typing import Optional


class LocalLLMError(Exception):
    """Base exception for local LLM errors."""
    pass


class OllamaNotRunningError(LocalLLMError):
    """Raised when Ollama server is not accessible."""
    pass


class ModelNotFoundError(LocalLLMError):
    """Raised when requested model is not pulled."""
    pass


class OllamaAdapter:
    """
    Adapter cho Ollama REST API.

    Endpoint: http://localhost:11434/api/generate
    Docs: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    DEFAULT_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen2.5:latest"

    def __init__(
        self,
        base_url: str = DEFAULT_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = 120,
        temperature: float = 0.2,  # Low temperature for structured report generation
        max_tokens: int = 2000,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.max_tokens = max_tokens

    def is_running(self) -> bool:
        """Kiểm tra Ollama server có đang chạy không."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=3)
            return r.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self):
        """Trả về danh sách models đã pull."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            r.raise_for_status()
            data = r.json()
            return [m["name"] for m in data.get("models", [])]
        except requests.RequestException as e:
            raise OllamaNotRunningError(
                f"Không thể kết nối Ollama tại {self.base_url}. "
                f"Chạy 'ollama serve' trước. Lỗi: {e}"
            )

    def ensure_model(self):
        """Đảm bảo model đã được pull. Raise error nếu chưa."""
        if not self.is_running():
            raise OllamaNotRunningError(
                f"Ollama server không chạy tại {self.base_url}.\n"
                "Cài đặt: https://ollama.com/download\n"
                "Chạy: ollama serve\n"
                "Pull model: ollama pull qwen2.5:7b-instruct"
            )

        models = self.list_models()
        # Ollama tag names có thể có ":latest" suffix, nên match linh hoạt
        model_base = self.model.split(":")[0]
        if not any(m.startswith(model_base) for m in models):
            raise ModelNotFoundError(
                f"Model '{self.model}' chưa được pull.\n"
                f"Các models có sẵn: {models}\n"
                f"Pull model bằng: ollama pull {self.model}"
            )

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """
        Gửi prompt đến Ollama và nhận response.
        Sử dụng /api/chat endpoint (Ollama 0.30+).

        Args:
            prompt: User prompt
            system: System prompt (optional)

        Returns:
            Generated text từ model

        Raises:
            OllamaNotRunningError: nếu server không chạy
            ModelNotFoundError: nếu model chưa pull
            LocalLLMError: nếu có lỗi khác
        """
        self.ensure_model()

        # Build messages array for /api/chat
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }

        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout,
            )
            r.raise_for_status()
            data = r.json()
            # /api/chat returns response in message.content
            return data.get("message", {}).get("content", "").strip()

        except requests.Timeout:
            raise LocalLLMError(
                f"Ollama timeout sau {self.timeout}s. "
                "Thử tăng timeout hoặc giảm max_tokens."
            )
        except requests.RequestException as e:
            raise LocalLLMError(f"Lỗi gọi Ollama: {e}")


class LocalLLMClient:
    """
    High-level client: tự động chọn adapter phù hợp.
    Hiện tại chỉ hỗ trợ Ollama, có thể mở rộng cho vLLM, llama.cpp.
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        if backend == "ollama":
            self.adapter = OllamaAdapter(
                base_url=base_url or OllamaAdapter.DEFAULT_URL,
                model=model or OllamaAdapter.DEFAULT_MODEL,
                **kwargs,
            )
        else:
            raise ValueError(
                f"Backend '{backend}' chưa được hỗ trợ. "
                "Hiện tại chỉ hỗ trợ: ollama"
            )

    def generate(self, prompt: str, system: Optional[str] = None) -> str:
        """Gửi prompt và nhận response."""
        return self.adapter.generate(prompt, system)

    def is_ready(self) -> bool:
        """Kiểm tra backend + model có sẵn sàng không."""
        try:
            self.adapter.ensure_model()
            return True
        except LocalLLMError:
            return False

    def diagnose(self) -> str:
        """Trả về chuỗi chẩn đoán trạng thái backend."""
        lines = [f"Backend: {type(self.adapter).__name__}"]

        if not self.adapter.is_running():
            lines.append("[FAIL] Server không chạy")
            lines.append("   Fix: ollama serve")
            return "\n".join(lines)

        lines.append("[OK] Server đang chạy")

        try:
            models = self.adapter.list_models()
            lines.append(f"[OK] Models đã pull: {models}")

            model_base = self.adapter.model.split(":")[0]
            if any(m.startswith(model_base) for m in models):
                lines.append(f"[OK] Model '{self.adapter.model}' sẵn sàng")
            else:
                lines.append(f"[FAIL] Model '{self.adapter.model}' chưa pull")
                lines.append(f"   Fix: ollama pull {self.adapter.model}")
        except LocalLLMError as e:
            lines.append(f"[FAIL] {e}")

        return "\n".join(lines)


if __name__ == "__main__":
    # Chạy chẩn đoán
    client = LocalLLMClient()
    print("=" * 60)
    print("Local LLM Diagnostic")
    print("=" * 60)
    print(client.diagnose())
    print("=" * 60)

    # Test nhanh nếu ready
    if client.is_ready():
        print("\nTest generation:")
        response = client.generate("Xin chào, hãy giới thiệu bản thân trong 1 câu.")
        print(f"Response: {response}")
