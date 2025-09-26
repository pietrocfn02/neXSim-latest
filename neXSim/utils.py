class SingletonMeta(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]

import re

BABELNET_PATTERN = re.compile(r"^bn:\d{8}[nvar]$")

def is_valid_babelnet_id(candidate: str) -> bool:
    """
    Format: bn:<8-digit number><letter in {n,v,a,r}>
    """
    return bool(BABELNET_PATTERN.match(candidate))



def pred_identifier_to_displayed_name(pred_identifier: str) -> str:
    return pred_identifier.replace("_", " ").title()


def pred_identifier_to_ontological_name(pred_identifier: str) -> str:
    return pred_identifier

def pred_identifier_to_clingo_relation(pred_identifier: str) -> str:
    return pred_identifier.replace(" ", "_").lower()
