from dataclasses import dataclass


@dataclass(frozen=True)
class MockTransferResult:
    accepted: bool
    message: str


class MockTelephonyProvider:
    def transfer_call(self, destination: str) -> MockTransferResult:
        return MockTransferResult(True, f"Simulated transfer to {destination}")


class MockNotificationProvider:
    def send_confirmation(self, recipient: str, message: str) -> str:
        return f"mock-notification:{recipient}:{len(message)}"
