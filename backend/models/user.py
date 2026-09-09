from dataclasses import dataclass
from typing import Any, Dict

# pyrefly: ignore [missing-import]
from bson import ObjectId


@dataclass
class User:
	id: ObjectId
	email: str
	password_hash: bytes
	name: str

	@staticmethod
	def from_mongo(doc: Dict[str, Any]) -> "User":
		return User(
			id=doc.get("_id"),
			email=doc.get("email", ""),
			password_hash=doc.get("password_hash", b""),
			name=doc.get("name", ""),
		)
