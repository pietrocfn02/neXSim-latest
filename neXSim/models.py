from enum import Enum
from typing import List, Union, Optional, Any

from pydantic import BaseModel, Field
from typing_extensions import Annotated
from neXSim.utils import is_valid_babelnet_id


class EntityType(str, Enum):
    CONCEPT = "CONCEPT"
    NAMED_ENTITY = "NAMED_ENTITY"


def validate_babelnet_id(v: str) -> str:
    if not is_valid_babelnet_id(v):
        raise ValueError(f"Invalid BabelNet ID: {v}")
    return v


BabelNetID = Annotated[str, validate_babelnet_id]


class Entity(BaseModel):
    id: BabelNetID
    main_sense: str
    description: str = Field(default="")
    synonyms: List[str] = Field(default_factory=list)
    entity_type: "EntityType" = Field(default="NAMED_ENTITY")  # if enum default
    image_url: str = Field(default="")

    class Config:
        frozen = True  # makes objects immutable & hashable

    @property
    def shown_name(self) -> str:
        return self.main_sense.replace("_", " ")

    def __hash__(self):
        return hash(self.id)


class EntityList(BaseModel):
    entities: List[Entity]


class Variable(BaseModel):
    origin: List[BabelNetID] = Field(default_factory=list)
    is_free: bool = False
    nominal: int = 0

    class Config:
        frozen = True

    def __eq__(self, other) -> bool:
        if not isinstance(other, Variable):
            return NotImplemented
        return str(self) == str(other)

    def __str__(self):
        return f"{'X' if self.is_free else 'Y'}_{self.nominal}"

    def __hash__(self) -> int:
        return hash(str(self))


class Atom(BaseModel):
    source_id: Union[BabelNetID, Variable]
    target_id: Union[BabelNetID, Variable]
    predicate: str

    class Config:
        frozen = True

    @staticmethod
    def _multiply_term(lhs: Union[BabelNetID, Variable], rhs: Union[BabelNetID, Variable]) \
            -> Union[BabelNetID, Variable]:

        if type(lhs) == str and type(rhs) == str and lhs == rhs:
            return lhs

        out = Variable(origin=[], is_free=False, nominal=0)

        if type(lhs) == str:
            out.origin.append(lhs)
        else:
            out.origin.extend(lhs.origin)
        if type(rhs) == str:
            out.origin.append(rhs)
        else:
            out.origin.extend(rhs.origin)

        return out

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Atom):
            return NotImplemented
        if self.predicate != other.predicate:
            return False
        if type(self.source_id) != type(other.source_id):
            return False
        if type(self.target_id) != type(other.target_id):
            return False

        return self.source_id == other.source_id and self.target_id == other.target_id

    def multiply(self, other: "Atom") -> "Atom":
        if type(self) != type(other):
            return NotImplemented

        if self.predicate != other.predicate:
            return NotImplemented

        new_source = Atom._multiply_term(self.source_id, other.source_id)
        new_target = Atom._multiply_term(self.target_id, other.target_id)
        return Atom(source_id=new_source, target_id=new_target, predicate=self.predicate)

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.predicate))


class SearchByIdResponse(BaseModel):
    entities: list[Entity]


class Summary(BaseModel):
    entity: BabelNetID
    summary: list[Atom]
    tops: list[BabelNetID]

    def __lt__(self, other):
        if type(other) is not type(self):
            raise TypeError(f"Cannot compare {type(self)} and {type(other)}")
        return len(self.summary) < len(other.summary)


class NeXSimResponse(BaseModel):
    unit: list[BabelNetID]
    summaries: Optional[list[Summary]] = None
    lca: Optional[list[Atom]] = None
    characterization: Optional[list[Atom]] = None
    kernel_explanation: Optional[list[Atom]] = None
    computation_times: Optional[dict[str, float]] = None
