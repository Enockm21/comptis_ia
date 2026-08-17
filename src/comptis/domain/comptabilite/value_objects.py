from enum import StrEnum


class StatutEcriture(StrEnum):
    A_CATEGORISER = "a_categoriser"  # compte_id est NULL — seul statut atteint par cette brique
    CATEGORISEE = "categorisee"      # compte proposé par le moteur (brique SP4)
    VALIDEE = "validee"              # confirmée par un humain (brique SP5)
