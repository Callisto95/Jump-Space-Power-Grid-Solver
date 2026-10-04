import tomllib
from dataclasses import dataclass
from enum import auto, Enum, StrEnum
from glob import glob
from typing import Generator

import questionary
from questionary import Choice

from algorithm_x import algorithm_x
from matrix import generate_rotations, Matrix, NamedMatrix

type HullLimitations = dict[str, int]


class PowergridCellType(Enum):
    EMPTY = auto()
    UNPROTECTED = auto()
    PROTECTED = auto()


class MatrixMappings(dict, Enum):
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


@dataclass(frozen=True)
class Placement:
    x: int
    y: int
    
    def __str__(self) -> str:
        return f"({self.x}x{self.y})"


@dataclass(frozen=True)
class ShipModule:
    name: str
    matrix: Matrix
    
    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class HullModule(ShipModule):
    matrix: Matrix[bool]


@dataclass(frozen=True)
class PowerModule(ShipModule):
    matrix: Matrix[PowergridCellType]


class Powergrid:
    def __init__(
        self,
        *modules: PowerModule,
    ):
        if len(modules) == 0:
            raise ValueError("The powergrid must contain at least one generator")
        
        matrix_width: int = modules[0].matrix.width
        
        if any(module.matrix.width != matrix_width for module in modules):
            raise ValueError("Cannot create a power grid from reactors and generators of different width")
        
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
                    # an empty cell is supposed to be used
                    return None
                
                if not module_cell:
                    # module isn't on this cell
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
        
        raise ValueError(f"The cell at {row}-{column} (is {self.matrix.get_cell(row, column)}) doesn't have an index.")
    
    def index_to_cell(self, index: int) -> PowergridCellType:
        if index >= self.matrix.weight(MatrixMappings.POWER_GRID_WEIGHT):
            raise ValueError("index is too big for the powergrid")
        
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
    
    def find_placement(self, rotated_matrix: Matrix[bool]) -> Generator[tuple[list[int], Placement]]:
        for y_offset in range(self.matrix.height - rotated_matrix.height + 1):
            for x_offset in range(self.matrix.width - rotated_matrix.width + 1):
                position: Placement = Placement(x_offset, y_offset)
                used_indices: list[int] | None = self.place(rotated_matrix, position)
                
                if used_indices is None:
                    continue
                
                yield used_indices, position


class ModuleType(StrEnum):
    POWER = "power"
    MODULE = "module"


@dataclass(frozen=True)
class ModuleConfiguration:
    type: ModuleType
    available_modules: list[ShipModule]


EMPTY_GENERATOR = PowerModule("Empty (P)", Matrix([[PowergridCellType.EMPTY] * 8] * 2))
EMPTY_MODULE = HullModule("Empty (M)", Matrix([]))


def load_configurations() -> tuple[dict[str, dict[str, int]], dict[str, ModuleConfiguration]]:
    with open("./resources/ship-configuration.toml", "rb") as ship_configuration_file:
        config: dict[str, dict[str, int | str]] = tomllib.load(ship_configuration_file)
    
    module_types: dict[str, ModuleType] = config["module-types"]
    
    if any(module_type not in list(ModuleType) for module_type in module_types.values()):
        raise ValueError(f"A module is misconfigured. Accepted types are {', '.join(list(ModuleType))}")
    
    module_configurations: dict[str, ModuleConfiguration] = { }
    for module_name in module_types:
        available_modules: list[ShipModule] = []
        
        for module_file in glob(f"./resources/{module_name}/*.txt"):
            module_matrix: NamedMatrix[str] = NamedMatrix.load_from_file(module_file)
            
            if module_types[module_name] == ModuleType.MODULE:
                available_modules.append(HullModule(module_matrix.name, module_matrix.map(MatrixMappings.MODULE)))
            elif module_types[module_name] == ModuleType.POWER:
                available_modules.append(PowerModule(module_matrix.name, module_matrix.map(MatrixMappings.POWER)))
        
        module_configurations[module_name] = ModuleConfiguration(module_types[module_name], available_modules)
    
    ships: dict[str, HullLimitations] = config["ships"]
    
    for name, limits in ships.items():
        if module_types.keys() != limits.keys():
            raise ValueError(f"Ship limits don't match for hull {name}, {limits.keys()} should ALL be set")
    
    return ships, module_configurations


def show_current_status(
    hull_name: str,
    limitations: HullLimitations,
    module_selections: dict[str, list[ShipModule]],
) -> None:
    display_names: dict[str, str] = {
        module_name: module_name if limitations[module_name] != 1 else module_name[:-1]
        for module_name in module_selections
    }
    display_length: int = max(len(module_name) for module_name in display_names.values())
    
    print("---", hull_name, "---")
    for module_name in limitations:
        selected_modules: list[ShipModule] = module_selections[module_name]
        module_limit: int = limitations[module_name]
        
        empty_count: int = selected_modules.count(EMPTY_GENERATOR) + selected_modules.count(EMPTY_MODULE)
        
        print(
            f"{display_names[module_name]: <{display_length}} ({module_limit - empty_count}/{module_limit}): ",
            end="",
        )
        
        if module_limit == 0:
            print("not applicable")
        else:
            print(", ".join(str(module) for module in module_selections[module_name]))


def create_menu_choices(limitations: HullLimitations) -> list[Choice]:
    choices: list[Choice] = []
    for module_category in limitations:
        display_name: str = module_category.replace("-", " ")
        
        if limitations[module_category] == 1:
            display_name = display_name[:-1]
        
        choices.append(Choice(f"change {display_name}", value=module_category))
    
    choices.append(Choice("change ship"))
    choices.append(Choice("compute solution"))
    choices.append(Choice("exit"))
    return choices


@dataclass(frozen=True)
class PlacedModule:
    module: HullModule
    module_number: int
    matrix: Matrix[bool]
    position: Placement
    used_indices: list[int]


def compute_solution(
    selections: dict[str, list[ShipModule]],
    module_config: dict[str, ModuleConfiguration],
) -> Generator[list[PlacedModule]]:
    # this isn't really dynamic like the rest, but the order (top to bottom) is important
    power_modules: list[PowerModule] = selections["reactors"] + selections["auxiliary-generators"]
    
    # should never happen, here to stop something bad
    if any(not isinstance(power_module, PowerModule) for power_module in power_modules):
        raise ValueError("a power module is not a actually a power module")
    
    powergrid: Powergrid = Powergrid(*power_modules)
    
    all_modules: list[HullModule] = []
    module_count: int = 0
    
    for module_name, configuration in module_config.items():
        if configuration.type == ModuleType.POWER:
            continue
        
        # not anything on the powergrid, so empty slots are irrelevant
        current_modules: list[HullModule] = list(
            filter(
                lambda module: not (module is EMPTY_MODULE or module is EMPTY_GENERATOR),
                selections[module_name],
            ),
        )
        
        all_modules += current_modules
        module_count += len(current_modules)
    
    # should never happen, here to stop something bad
    if any(not isinstance(module, HullModule) for module in all_modules):
        raise ValueError("not all placeable modules are actually modules")
    
    all_placements: list[PlacedModule] = []
    for module_index, module in enumerate(all_modules):
        for rotated_matrix in generate_rotations(module.matrix):
            found_solution: bool = False
            
            for used_indices, position in powergrid.find_placement(rotated_matrix):
                all_placements.append(PlacedModule(module, module_index, rotated_matrix, position, used_indices))
                found_solution = True
            
            if not found_solution:
                (questionary
                 .press_any_key_to_continue(f"{module.name} cannot be placed at all.")
                 .ask())
                return
    
    matrix_width: int = module_count + powergrid.matrix.weight(MatrixMappings.POWER_GRID_WEIGHT)
    
    workspace: list[list[int]] = []
    for placed_module in all_placements:
        row = [0] * matrix_width
        
        row[placed_module.module_number] = 1
        
        for used_index in placed_module.used_indices:
            row[module_count + used_index] = 1
        
        workspace.append(row)
    
    yield from algorithm_x(Matrix(workspace), module_count, all_placements)


def select_module(
    module_limit: int,
    module_config: ModuleConfiguration,
    current_modules: list[ShipModule],
) -> list[ShipModule] | None:
    current_modules: list[ShipModule] = current_modules.copy()
    
    choices: list[Choice] = [Choice(module.name, value=module) for module in module_config.available_modules]
    choices.sort(key=lambda c: c.title)
    
    if module_config.type == ModuleType.POWER:
        choices.append(Choice(EMPTY_GENERATOR.name, value=EMPTY_GENERATOR))
    else:
        choices.append(Choice(EMPTY_MODULE.name, value=EMPTY_MODULE))
    
    for choice_index in range(module_limit):
        choice: ShipModule | None = questionary.select(
            f"Select module ({choice_index + 1}/{module_limit})",
            choices,
            qmark="",
            instruction=" ",
            default=current_modules[choice_index],  # questionary compares values, this is fine
        ).ask()
        
        if choice is None:
            return None
        
        current_modules[choice_index] = choice
    
    return current_modules


def initialize_selections(
    limitations: HullLimitations,
    module_config: dict[str, ModuleConfiguration],
) -> dict[str, list[ShipModule]]:
    module_selections: dict[str, list[ShipModule]] = { }
    
    for module_name in limitations:
        if len(module_config[module_name].available_modules) == 0:
            module_selections[module_name] = []
        elif module_config[module_name].type == ModuleType.POWER:
            module_selections[module_name] = [EMPTY_GENERATOR] * limitations[module_name]
        elif module_config[module_name].type == ModuleType.MODULE:
            module_selections[module_name] = [EMPTY_MODULE] * limitations[module_name]
    
    return module_selections


def adapt_selections(
    new_limitations: HullLimitations,
    previous_selection: dict[str, list[ShipModule]],
    module_config: dict[str, ModuleConfiguration],
) -> dict[str, list[ShipModule]]:
    new_selection: dict[str, list[ShipModule]] = { }
    
    for module_name, new_module_limit in new_limitations.items():
        if new_module_limit == 0:
            new_selection[module_name] = []
        
        cut_modules: list[ShipModule] = previous_selection[module_name][:new_module_limit]
        new_empty_modules: int = new_module_limit - len(cut_modules)
        
        if module_config[module_name].type == ModuleType.POWER:
            empty_module: ShipModule = EMPTY_GENERATOR
        else:
            empty_module: ShipModule = EMPTY_MODULE
        
        new_selection[module_name] = cut_modules + ([empty_module] * new_empty_modules)
    
    # print(new_selection)
    return new_selection


def main():
    hulls, module_configuration = load_configurations()
    
    # take the first and done
    selected_hull_name: str = next(iter(hulls.keys()))
    
    module_selections = initialize_selections(hulls[selected_hull_name], module_configuration)
    
    last_answer: str | None = None
    while True:
        show_current_status(selected_hull_name, hulls[selected_hull_name], module_selections)
        
        choices: list[Choice] = create_menu_choices(hulls[selected_hull_name])
        choice: str | None = questionary.select(
            "What to do with the ship?",
            choices,
            qmark="",
            instruction=" ",
            default=last_answer,
        ).ask()
        
        if choice is None or choice == "exit":
            return
        
        last_answer = choice
        
        if choice == "change ship":
            new_ship_name: str | None = questionary.select(
                "Select ship:",
                [Choice(ship_name) for ship_name in hulls],
                qmark="",
                instruction=" ",
            ).ask()
            
            if new_ship_name is None:
                print("keeping last ship")
                continue
            
            module_selections = adapt_selections(hulls[new_ship_name], module_selections, module_configuration)
            selected_hull_name = new_ship_name
            continue
        
        if choice == "compute solution":
            for solution_index, solution in enumerate(compute_solution(module_selections, module_configuration)):
                print(f"Solution #{solution_index}")
                for module in solution:
                    print(module.module.name, "@", module.position)
                    print(module.matrix)
                print("-" * 50)
                
                do_continue: bool | None = questionary.confirm("Next solution?", qmark="", default=False).ask()
                
                if not do_continue:
                    break
            
            continue
        
        selected_modules: list[ShipModule] | None = select_module(
            hulls[selected_hull_name][choice],
            module_configuration[choice],
            module_selections[choice],
        )
        
        if selected_modules is None:
            continue
        
        module_selections[choice] = selected_modules


if __name__ == "__main__":
    try:
        main()
    except EOFError:
        pass
