"""
Tool definitions and execution for NDAI attestation verification.

Provides a provider-agnostic tool schema and verification execution logic
that wraps the Tinfoil SDK. Used by A2 (attested privacy) and A3 (invalid
attestation) privacy levels.
"""

import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Provider-agnostic tool definition ──────────────────────────────────────

VERIFY_ENCLAVE_TOOL = {
    "name": "verify_enclave",
    "description": (
        "Verify the cryptographic attestation of the NDAI privacy enclave. "
        "Calls the Tinfoil SDK to check that the enclave's code digest and "
        "hardware measurement match the expected values published on GitHub "
        "and signed via Sigstore. Returns verification status, code digest, "
        "and hardware measurement if successful."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "enclave_url": {
                "type": "string",
                "description": "The enclave endpoint URL to verify.",
            },
            "repo": {
                "type": "string",
                "description": "The GitHub repository containing the expected enclave code.",
            },
        },
        "required": ["enclave_url", "repo"],
    },
}

# ── Default enclave configuration ──────────────────────────────────────────

DEFAULT_ENCLAVE_URL = "ndai-enclave.3-14.containers.tinfoil.sh"
DEFAULT_REPO = "rkdud007/compatibility-tinfoil"


# ── Verification result ────────────────────────────────────────────────────


@dataclass
class VerificationResult:
    """Result of an enclave verification attempt."""

    verified: bool
    enclave_url: str
    repo: str
    code_digest: Optional[str] = None
    hardware_measurement: Optional[str] = None
    public_key: Optional[str] = None
    error: Optional[str] = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))


# ── Execution ──────────────────────────────────────────────────────────────


def execute_verify_enclave(
    arguments: Dict[str, Any],
    *,
    force_failure: bool = False,
) -> VerificationResult:
    """
    Execute the verify_enclave tool call.

    For A2 (force_failure=False): runs real Tinfoil SDK verification.
    For A3 (force_failure=True): returns a simulated verification failure.
    """
    enclave_url = arguments.get("enclave_url", DEFAULT_ENCLAVE_URL)
    repo = arguments.get("repo", DEFAULT_REPO)

    if force_failure:
        return VerificationResult(
            verified=False,
            enclave_url=enclave_url,
            repo=repo,
            error=(
                "ATTESTATION FAILED: The enclave's code digest does not match "
                "the expected value published on GitHub. The enclave binary may "
                "have been tampered with. Hardware measurement verification also "
                "failed — the TEE quote signature is invalid. DO NOT TRUST this "
                "enclave with sensitive information."
            ),
        )

    try:
        from tinfoil.client import SecureClient

        client = SecureClient(enclave=enclave_url, repo=repo)
        ground_truth = client.verify()

        return VerificationResult(
            verified=True,
            enclave_url=enclave_url,
            repo=repo,
            code_digest=str(ground_truth.digest),
            hardware_measurement=str(ground_truth.measurement),
            public_key=str(ground_truth.public_key),
        )
    except Exception as e:
        logger.error("Enclave verification failed: %s", e, exc_info=True)
        return VerificationResult(
            verified=False,
            enclave_url=enclave_url,
            repo=repo,
            error=f"Verification error: {type(e).__name__}: {e}",
        )


# ── Provider-specific tool format converters ───────────────────────────────


def tool_to_openai_format() -> dict:
    """Convert the tool definition to OpenAI function calling format."""
    return {
        "type": "function",
        "function": {
            "name": VERIFY_ENCLAVE_TOOL["name"],
            "description": VERIFY_ENCLAVE_TOOL["description"],
            "parameters": VERIFY_ENCLAVE_TOOL["parameters"],
        },
    }


def tool_to_anthropic_format() -> dict:
    """Convert the tool definition to Anthropic tool use format."""
    return {
        "name": VERIFY_ENCLAVE_TOOL["name"],
        "description": VERIFY_ENCLAVE_TOOL["description"],
        "input_schema": VERIFY_ENCLAVE_TOOL["parameters"],
    }


def tool_to_gemini_format():
    """Convert the tool definition to Gemini function declaration format."""
    import google.generativeai as genai

    return genai.types.FunctionDeclaration(
        name=VERIFY_ENCLAVE_TOOL["name"],
        description=VERIFY_ENCLAVE_TOOL["description"],
        parameters=VERIFY_ENCLAVE_TOOL["parameters"],
    )
