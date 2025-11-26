from reactivated import template
from typing import NamedTuple


@template
class MyTemplate(NamedTuple):
    name: str
    title: str
    age: int
    location: str