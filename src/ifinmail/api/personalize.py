"""Placeholder replacement for personalised org mail delivery.

Supported placeholders in subject and body:
  {name}       → member's first name
  {first_name} → member's first name
  {full_name}  → member's first + last name (trimmed)
  {email}      → member's email address
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MemberInfo:
    first_name: str
    last_name: str
    email: str


def personalise(text: str, member: MemberInfo) -> str:
    """Replace placeholders with the given member's info."""
    return (
        text.replace("{name}", member.first_name)
        .replace("{first_name}", member.first_name)
        .replace("{full_name}", f"{member.first_name} {member.last_name}".strip())
        .replace("{email}", member.email)
    )
