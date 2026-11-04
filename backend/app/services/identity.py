import re


_CREATOR_ANSWER = "I am Max-AI. I was created by A-maxcode, also known as Angelo Besas."
_DEVELOPER_ANSWER = "I am Max-AI. My developer is A-maxcode, also known as Angelo Besas."
_BUILDER_ANSWER = "I am Max-AI. I was built by A-maxcode, also known as Angelo Besas."
_OWNER_ANSWER = "I am Max-AI. I was developed by A-maxcode, also known as Angelo Besas."
_NAME_ANSWER = "My name is Max-AI."
_CREATOR_DETAILS = (
    "A-maxcode, also known as Angelo Besas, developed the Max-AI assistant "
    "application. A-maxcode did not create the underlying SmolLM2 foundation model."
)
_ABOUT_ANSWER = (
    "I am Max-AI, an AI assistant developed by A-maxcode, also known as "
    "Angelo Besas. A-maxcode developed the Max-AI assistant application and "
    "did not create the underlying SmolLM2 foundation model."
)
_ASSISTANT_ANSWER = (
    "I am Max-AI, an AI assistant developed by A-maxcode, also known as Angelo Besas."
)


def identity_reply(message: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", " ", message.casefold()).strip()
    normalized = re.sub(r"\ba\s*max\s*code\b|\bamaxcode\b", "amaxcode", normalized)

    if re.search(r"\bwho (?:is|was) (?:angelo besas|amaxcode)\b", normalized):
        return _CREATOR_DETAILS

    if re.search(
        r"\b(?:tell me about|describe) (?:your )?(?:creator|developer|builder)\b"
        r"|\bwho is (?:the )?(?:person|developer|creator) behind "
        r"(?:you|max ai|this assistant)\b"
        r"|\bwhere did you come from\b",
        normalized,
    ):
        return _ABOUT_ANSWER

    if re.search(
        r"\bwho (?:is|was) (?:your )?(?:developer|creator)\b"
        r"|\bwho s (?:your )?(?:developer|creator)\b"
        r"|\bwho (?:developed|created|made) (?:you|max ai|this assistant)\b",
        normalized,
    ):
        return _DEVELOPER_ANSWER if "developer" in normalized else _CREATOR_ANSWER

    if re.search(
        r"\bwho (?:is|was) (?:your )?(?:builder|owner)\b"
        r"|\bwho owns (?:you|max ai|this assistant)\b"
        r"|\bwho built (?:you|max ai|this assistant)\b",
        normalized,
    ):
        return (
            _OWNER_ANSWER
            if re.search(r"\bowner\b|\bowns\b", normalized)
            else _BUILDER_ANSWER
        )

    if re.search(
        r"\bwhat (?:is|s) your name\b"
        r"|\bwho are you\b"
        r"|\bwhat (?:ai|assistant) are you\b"
        r"|\bare you (?:chatgpt|max ai) or (?:chatgpt|max ai)\b",
        normalized,
    ):
        if "name" in normalized:
            return _NAME_ANSWER
        return _ASSISTANT_ANSWER

    return None
