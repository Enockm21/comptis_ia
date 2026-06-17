from enum import StrEnum


class OrgType(StrEnum):
    EDITEUR = "editeur"
    CABINET = "cabinet"
    PME_DIRECTE = "pme_directe"


class Role(StrEnum):
    OWNER = "owner"
    ACCOUNTANT = "accountant"
    VIEWER = "viewer"
