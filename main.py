import copy
import tomllib
from dataclasses import dataclass
from enum import auto, Enum, StrEnum
from glob import glob

import questionary
from questionary import Choice

from algorithm_x import algorithm_x
from matrix import generate_rotations, Matrix, NamedMatrix


class PowergridCellType(Enum):
    EMPTY = auto()
    UNPROTECTED = auto()
    PROTECTED = auto()


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    
    def __str__(self) -> str:
        return f"({self.x}-{self.y})"


@dataclass(frozen=True)
class HullModule:
    name: str
    matrix: Matrix
    
    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class ShipModule(HullModule):
    matrix: Matrix[bool]


@dataclass(frozen=True)
class PowerModule(HullModule):
    matrix: Matrix[PowergridCellType]


class Powergrid:
    def __init__(
        self,
        *modules: PowerModule,
    ):
        if len(modules) == 0:
            raise ValueError("The powergrid must contain at least one generator")
        
        grid_width: int = modules[0].matrix.width
        
        if any(module.matrix.width != grid_width for module in modules):
            raise ValueError("Cannot create a power grid from generators of different width")
        
        matrix_data: list[list[PowergridCellType]] = []
        
        for module in modules:
            matrix_data += module.matrix.data()
        
        self.matrix: Matrix[PowergridCellType] = Matrix(matrix_data)
    
    # returns the indices of used cells, None if no placement is possible
    def place(self, module: Matrix[bool], position: Placement) -> list[int] | None:
        # bounding checks
        if (
            module.width + position.x > self.matrix.width
            or module.height + position.y > self.matrix.height
        ):
            # print("bounding failed")
            return None
        
        used_cells_indices: list[int] = []
        
        for relative_row in range(module.height):
            for relative_column in range(module.width):
                row: int = relative_row + position.y
                column: int = relative_column + position.x
                
                cell: PowergridCellType = self.matrix.get_cell(row, column)
                module_cell: bool = module.get_cell(relative_row, relative_column)
                
                if module_cell and cell == PowergridCellType.EMPTY:
                    # print("uses bad cell")
                    return None
                
                if not module_cell:
                    continue
                
                used_cells_indices.append(self.cell_to_index(row, column))
        
        return used_cells_indices
    
    def cell_to_index(self, row: int, column: int) -> int:
        if row >= self.matrix.height or column >= self.matrix.width:
            raise ValueError(
                f"The cell {row}-{column} is not in the powergrid (max {self.matrix.height}-{self.matrix.width})",
            )
        
        index = 0
        
        for y in range(self.matrix.height):
            for x in range(self.matrix.width):
                if x == column and y == row:
                    return index
                
                if self.matrix.get_cell(y, x) == PowergridCellType.EMPTY:
                    continue
                
                index += 1
        
        raise ValueError(f"The cell at {row}-{column} doesn't have an index. Is it an empty cell?")
    
    def index_to_cell(self, index: int) -> PowergridCellType:
        current_index: int = 0
        
        for y in range(self.matrix.height):
            for x in range(self.matrix.width):
                current_cell: PowergridCellType = self.matrix.get_cell(y, x)
                
                if current_cell == PowergridCellType.EMPTY:
                    continue
                
                if current_index == index:
                    return current_cell
                
                current_index += 1
        
        raise ValueError(f"The given index {index} is too big for the matrix (max index is {current_index - 1})")


type HullLimitations = dict[str, int]


class ModuleType(StrEnum):
    POWER = "power"
    MODULE = "module"


class MatrixMappings(Enum):
    POWER = {
        "U": PowergridCellType.UNPROTECTED,
        "P": PowergridCellType.PROTECTED,
        "_": PowergridCellType.EMPTY,
    }
    MODULE = { "X": True, "_": False }
    POWER_GRID_WEIGHT = {
        PowergridCellType.EMPTY      : False,
        PowergridCellType.PROTECTED  : True,
        PowergridCellType.UNPROTECTED: True,
    }


def load_configurations() -> tuple[dict[str, dict[str, int]], dict[str, list[HullModule]]]:
    with open("./resources/ship-configuration.toml", "rb") as ship_configuration_file:
        config: dict[str, dict[str, int | str]] = tomllib.load(ship_configuration_file)
    
    module_types: dict[str, ModuleType] = config["module-types"]
    if any(module_type not in list(ModuleType) for module_type in module_types.values()):
        raise ValueError(f"A module is misconfigured. Accepted types are {', '.join(list(ModuleType))}")
    
    available_modules: dict[str, list[HullModule]] = { }
    for module_name in module_types:
        for module_file in glob(f"./resources/{module_name}/*.txt"):
            module_matrix: NamedMatrix[str] = NamedMatrix.load_from_file(module_file)
            current_list: list[HullModule] = available_modules.setdefault(module_name, [])
            
            if module_types[module_name] == ModuleType.MODULE:
                current_list.append(ShipModule(module_matrix.name, module_matrix.map(MatrixMappings.MODULE.value)))
            elif module_types[module_name] == ModuleType.POWER:
                current_list.append(PowerModule(module_matrix.name, module_matrix.map(MatrixMappings.POWER.value)))
    
    ships: dict[str, HullLimitations] = config["ships"]
    for name, limits in ships.items():
        if module_types.keys() != limits.keys():
            raise ValueError(f"Ship limits don't match for hull {name}")
    
    return ships, available_modules


def show_current_status(
    hull_name: str,
    hull_limitations: HullLimitations,
    module_selections: dict[str, list[HullModule]],
) -> None:
    display_names: dict[str, str] = {
        module_name: module_name if hull_limitations[module_name] != 1 else module_name[:-1]
        for module_name in module_selections
    }
    display_length: int = max(len(module_name) for module_name in display_names.values())
    
    print("---", hull_name, "---")
    for module_name in hull_limitations:
        print(
            f"{display_names[module_name]: <{display_length}} ({len(module_selections[module_name])}/"
            f"{hull_limitations[module_name]}): ",
            end="",
        )
        
        if len(module_selections[module_name]) == 0:
            print("None")
        else:
            print(", ".join(str(module) for module in module_selections[module_name]))


def create_menu_choices(hull_limitations: HullLimitations) -> list[Choice]:
    choices: list[Choice] = []
    for limit in hull_limitations:
        limit_name: str = limit.replace("-", " ")
        
        if hull_limitations[limit] == 1:
            limit_name = limit_name[:-1]
        
        choices.append(
            Choice(f"change {limit_name}", value=limit),
        )
    
    choices.append(Choice("change ship"))
    choices.append(Choice("compute solution"))
    choices.append(Choice("Exit", value="<<EXIT>>"))
    return choices


def compute_solution(selections: dict[str, list[HullModule]]) -> None:
    if len(selections["reactors"]) == 0:
        raise ValueError("No engines selected")
    
    reactor: PowerModule = selections["reactors"][0]
    if not isinstance(reactor, PowerModule):
        raise ValueError("reactor is not a power module")
    
    if not all(isinstance(generator, PowerModule) for generator in selections["auxiliary-generators"]):
        raise ValueError("an auxiliary generator is not a power module")
    
    powergrid: Powergrid = Powergrid(reactor, *selections["auxiliary-generators"])
    
    modules_to_place: dict[str, list[HullModule]] = copy.deepcopy(selections)
    for category in filter(lambda c: len(selections[c]) == 0 or isinstance(selections[c][0], PowerModule), selections):
        # print("removing", category)
        modules_to_place.pop(category)
    
    module_count: int = 0
    for modules in modules_to_place.values():
        module_count += len(modules)
    
    all_modules: list[ShipModule] = []
    for modules in modules_to_place.values():
        all_modules += modules
    
    if not all(isinstance(module, ShipModule) for module in all_modules):
        raise ValueError("not all placeable modules are actually modules")
    
    all_placements: list[tuple[ShipModule, Matrix[bool], Placement, list[int], int]] = []
    module_indices: list[int] = []
    module_index: int = 0
    for module in all_modules:
        for rotation_degree, rotation in enumerate(generate_rotations(module.matrix)):
            rotation_degree *= 90
            # split this into a function
            for y_offset in range(powergrid.matrix.height - rotation.height + 1):
                for x_offset in range(powergrid.matrix.width - rotation.width + 1):
                    position: Placement = Placement(x_offset, y_offset)
                    used_indices = powergrid.place(rotation, position)
                    
                    if used_indices is None:
                        continue
                    
                    all_placements.append((module, rotation, position, used_indices, rotation_degree))
                    module_indices.append(module_index)
        
        module_index += 1
    
    named_placements: list[tuple[ShipModule, Matrix[bool], Placement]] = [
        (module, rotated_matrix, position)
        for module, rotated_matrix, position, used_indices, rotation_degree
        in all_placements
    ]
    
    matrix_width: int = module_count + powergrid.matrix.weight(MatrixMappings.POWER_GRID_WEIGHT.value)
    
    workspace: list[list[int]] = []
    for index, value in enumerate(all_placements):
        module, _, position, used_indices, _ = value
        row = [0] * matrix_width
        
        for used_index in used_indices:
            row[module_count + used_index] = 1
        
        row[module_indices[index]] = 1
        
        workspace.append(row)
    
    # print(Matrix(workspace))
    
    for solution_index, solution in enumerate(algorithm_x(Matrix(workspace), module_count, named_placements)):
        print(f"Solution #{solution_index}")
        for module, matrix, position in solution:
            print(module.name, "@", position)
            print(matrix)
            print()
        print("-" * 50)
    
    questionary.press_any_key_to_continue("waiting...").ask()


def change_ship(
    all_hulls: dict[str, dict[str, int]],
    module_selections: dict[str, list[HullModule]],
    selected_hull_name: str,
) -> tuple[str, dict[str, list[HullModule]]]:
    ship_choice: str | None = questionary.select(
        "Select ship:",
        [Choice(ship_name) for ship_name in all_hulls],
        qmark="",
        instruction=" ",
    ).ask()
    
    if ship_choice is None:
        print("Keeping last choice")
    else:
        selected_hull_name = ship_choice
        module_selections: dict[str, list[HullModule]] = {
            module_name: module_selections[module_name][:all_hulls[selected_hull_name][module_name]]
            for module_name in all_hulls[selected_hull_name]
        }
    
    return selected_hull_name, module_selections


def select_module(
    module_limit: int,
    available_modules: list[HullModule],
    current_modules: list[HullModule],
) -> list[HullModule] | None:
    module_choices: list[HullModule] = []
    
    choices: list[Choice] = [Choice(module.name, value=module) for module in available_modules]
    choices.append(Choice("Leave empty", value="<<EMPTY>>"))
    
    for current_choice_number in range(module_limit):
        choice: HullModule | None = questionary.select(
            f"Select module ({current_choice_number}/{module_limit})",
            choices,
            qmark="",
            instruction=" ",
            default=(
                current_modules[current_choice_number]
                if len(current_modules) > current_choice_number
                else None
            ),
        ).ask()
        
        if choice is None:
            return None
        
        if choice == "<<EMPTY>>":
            return module_choices
        
        module_choices.append(choice)
    
    return module_choices


def main():
    all_hulls, available_modules = load_configurations()
    
    # take one for the beginning and done
    selected_hull_name: str = next(iter(all_hulls.keys()))
    module_selections: dict[str, list[HullModule]] = {
        module_name: [] for module_name in all_hulls[selected_hull_name]
    }
    
    while True:
        show_current_status(selected_hull_name, all_hulls[selected_hull_name], module_selections)
        
        choices = create_menu_choices(all_hulls[selected_hull_name])
        choice: str | None = questionary.select("What to do with the ship?", choices, qmark="", instruction=" ").ask()
        
        if choice is None or choice == "<<EXIT>>":
            return
        
        if choice == "change ship":
            selected_hull_name, module_selections = change_ship(
                all_hulls,
                module_selections,
                selected_hull_name,
            )
            continue
        
        if choice == "compute solution":
            compute_solution(module_selections)
            continue
        
        selected_modules: list[HullModule] | None = select_module(
            all_hulls[selected_hull_name][choice],
            available_modules[choice],
            module_selections[choice],
        )
        
        if selected_modules is None:
            continue
        
        module_selections[choice] = selected_modules


if __name__ == "__main__":
    main()
