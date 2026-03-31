#!/usr/bin/env python3
"""
R2 Upload Environment Checker

Verifies that all prerequisites for r2-upload are satisfied:
  1. Python version >= 3.8
  2. boto3 installed
  3. All required environment variables are set

Output (stdout, JSON):
  {
    "ok": true | false,
    "checks": [
      { "name": "...", "ok": true|false, "value": "...", "fix": "..." }
    ],
    "summary": "All checks passed." | "N check(s) failed. See above."
  }

Exit code: 0 if all checks pass, 1 otherwise.
"""

import json
import os
import sys


REQUIRED_ENV_VARS = [
    {
        "name": "R2_ACCOUNT_ID",
        "description": "Cloudflare Account ID",
        "example": "your-cloudflare-account-id",
        "where": "Cloudflare Dashboard → top-right corner",
    },
    {
        "name": "R2_ACCESS_KEY_ID",
        "description": "R2 API Token Key ID",
        "example": "your-r2-token-key-id",
        "where": "Cloudflare Dashboard → R2 → Manage API tokens",
    },
    {
        "name": "R2_SECRET_ACCESS_KEY",
        "description": "R2 API Token Secret",
        "example": "your-r2-token-secret",
        "where": "Cloudflare Dashboard → R2 → Manage API tokens",
    },
    {
        "name": "R2_BUCKET_NAME",
        "description": "Default R2 bucket name",
        "example": "my-assets",
        "where": "The name of your R2 bucket",
    },
    {
        "name": "R2_PUBLIC_URL",
        "description": "Public base URL for the bucket",
        "example": "https://pub-xxx.r2.dev",
        "where": "R2 bucket → Settings → Public Access domain",
    },
]


def check_python_version():
    major, minor = sys.version_info[:2]
    ok = (major, minor) >= (3, 8)
    return {
        "name": "python_version",
        "label": "Python 3.8+",
        "ok": ok,
        "value": f"{major}.{minor}.{sys.version_info[2]}",
        "fix": (
            None if ok
            else "Install Python 3.8 or later from https://python.org"
        ),
    }


def check_boto3():
    try:
        import boto3
        version = getattr(boto3, "__version__", "unknown")
        return {
            "name": "boto3",
            "label": "boto3 installed",
            "ok": True,
            "value": version,
            "fix": None,
        }
    except ImportError:
        return {
            "name": "boto3",
            "label": "boto3 installed",
            "ok": False,
            "value": None,
            "fix": "pip3 install boto3",
        }


def check_env_var(var_info: dict):
    name = var_info["name"]
    value = os.environ.get(name, "")
    ok = bool(value)
    masked = (value[:4] + "…" + value[-4:]) if len(value) > 10 else ("*" * len(value) if value else None)

    fix = (
        None if ok
        else (
            f"Add to ~/.zshrc or ~/.bashrc:\n"
            f"  export {name}=\"{var_info['example']}\"\n"
            f"  (Find it at: {var_info['where']})"
        )
    )

    # Extra format validation for R2_PUBLIC_URL
    if ok and name == "R2_PUBLIC_URL":
        if not value.startswith(("http://", "https://")):
            ok = False
            fix = (
                f"R2_PUBLIC_URL must start with https:// (got: {value!r}).\n"
                f"Update ~/.zshrc or ~/.bashrc:\n"
                f"  export R2_PUBLIC_URL=\"https://pub-xxx.r2.dev\""
            )

    return {
        "name": name,
        "label": f"${name} ({var_info['description']})",
        "ok": ok,
        "value": masked,
        "fix": fix,
    }


def main():
    checks = []
    checks.append(check_python_version())
    checks.append(check_boto3())
    for var_info in REQUIRED_ENV_VARS:
        checks.append(check_env_var(var_info))

    failed = [c for c in checks if not c["ok"]]
    all_ok = len(failed) == 0

    result = {
        "ok": all_ok,
        "checks": checks,
        "summary": (
            "All checks passed. Ready to upload."
            if all_ok
            else f"{len(failed)} check(s) failed. See 'fix' field for each failing item."
        ),
    }

    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
