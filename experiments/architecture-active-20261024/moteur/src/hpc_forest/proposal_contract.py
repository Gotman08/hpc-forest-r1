"""Transport-independent schema for one proposed source experiment."""

SOURCE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hypothesis": {"type": "string"},
        "transformations": {"type": "array", "items": {"type": "string"}},
        "sources_kept": {"type": "array", "items": {"type": "string"}},
        "files": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["hypothesis", "transformations", "sources_kept", "files", "notes"],
}
