from typing import Literal

MembershipRole = Literal["owner", "admin", "member"]
MembershipStatus = Literal["active", "invited", "suspended"]

ACTIVE_MEMBERSHIP_STATUS: MembershipStatus = "active"
OWNER_MEMBERSHIP_ROLE: MembershipRole = "owner"
