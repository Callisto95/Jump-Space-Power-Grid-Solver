import tomllib
from dataclasses import dataclass
from enum import auto, Enum, StrEnum
from glob import glob
from typing import Generator

import questionary

from algorithm_x import algorithm_x
from matrix import generate_rotations, Matrix, NamedMatrix

type HullLimitations = dict[str, int]


@dataclass(frozen=True)
class Colour:
    value: int
    
    @property
    def red(self) -> int:
        return (self.value >> 16) & 0xFF
    
    @property
    def green(self) -> int:
        return (self.value >> 8) & 0xFF
    
    @property
    def blue(self) -> int:
        return (self.value >> 0) & 0xFF


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
    row: int
    column: int
    
    def __str__(self) -> str:
        return f"(c{self.column} r{self.row})"


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


class Powergrid(Matrix[PowergridCellType]):
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
        
        super().__init__(matrix_data)
    
    def weight(self, mapping: dict[PowergridCellType, bool] | None = None) -> int:
        if mapping is None:
            mapping = MatrixMappings.POWER_GRID_WEIGHT
        
        return super().weight(mapping)
    
    # returns the indices of used cells, None if no placement is possible
    def place(self, module: Matrix[bool], position: Placement) -> list[int] | None:
        # bounding checks
        if (
            module.width + position.column > self.width
            or module.height + position.row > self.height
        ):
            # print("bounding failed")
            return None
        
        used_cells_indices: list[int] = []
        
        for relative_row in range(module.height):
            for relative_column in range(module.width):
                row: int = relative_row + position.row
                column: int = relative_column + position.column
                
                cell: PowergridCellType = self.get_cell(row, column)
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
        if row >= self.height or column >= self.width:
            raise ValueError(
                f"The cell {row}-{column} is not in the powergrid (max {self.height}-{self.width})",
            )
        
        index = 0
        
        for y in range(self.height):
            for x in range(self.width):
                if x == column and y == row:
                    return index
                
                if self.get_cell(y, x) == PowergridCellType.EMPTY:
                    continue
                
                index += 1
        
        raise ValueError(f"The cell at {row}-{column} (is {self.get_cell(row, column)}) doesn't have an index.")
    
    def index_to_cell(self, index: int) -> PowergridCellType:
        if index >= self.weight():
            raise ValueError("index is too big for the powergrid")
        
        current_index: int = 0
        
        for y in range(self.height):
            for x in range(self.width):
                current_cell: PowergridCellType = self.get_cell(y, x)
                
                if current_cell == PowergridCellType.EMPTY:
                    continue
                
                if current_index == index:
                    return current_cell
                
                current_index += 1
        
        raise ValueError(f"The given index {index} is too big for the matrix (max index is {current_index - 1})")
    
    def find_placement(self, rotated_matrix: Matrix[bool]) -> Generator[tuple[list[int], Placement]]:
        for row_offset in range(self.height - rotated_matrix.height + 1):
            for column_offset in range(self.width - rotated_matrix.width + 1):
                position: Placement = Placement(row_offset, column_offset)
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


@dataclass(frozen=True)
class PlacedModule:
    module: HullModule
    module_number: int
    matrix: Matrix[bool]
    position: Placement
    used_indices: list[int]


@dataclass
class Solution(Matrix[PowergridCellType | PlacedModule]):
    powergrid: Powergrid
    modules: list[PlacedModule]
    
    def __init__(self, powergrid: Powergrid, modules: list[PlacedModule]):
        self.powergrid = powergrid
        self.modules = modules
        
        data: list[list[PowergridCellType | PlacedModule]] = []
        
        for row in range(powergrid.height):
            data.append([self._placement_at(row, column) for column in range(powergrid.width)])
        
        super().__init__(data)
    
    def _placement_at(self, row: int, column: int) -> PowergridCellType | PlacedModule:
        for module in self.modules:
            if (
                module.position.row <= row < module.position.row + module.matrix.height
                and
                module.position.column <= column < module.position.column + module.matrix.width
                and
                module.matrix.get_cell(row - module.position.row, column - module.position.column)
            ):
                return module
        
        return self.powergrid.get_cell(row, column)


def compute_solution(
    selections: dict[str, list[ShipModule]],
    module_config: dict[str, ModuleConfiguration],
) -> Generator[Solution]:
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
        found_placement: bool = False
        
        for rotated_matrix in generate_rotations(module.matrix):
            
            for used_indices, position in powergrid.find_placement(rotated_matrix):
                all_placements.append(PlacedModule(module, module_index, rotated_matrix, position, used_indices))
                found_placement = True
        
        if not found_placement:
            (questionary
             .press_any_key_to_continue(f"{module.name} cannot be placed at all.")
             .ask())
            return
    
    matrix_width: int = module_count + powergrid.weight()
    
    workspace: list[list[int]] = []
    for placed_module in all_placements:
        row = [0] * matrix_width
        
        row[placed_module.module_number] = 1
        
        for used_index in placed_module.used_indices:
            row[module_count + used_index] = 1
        
        workspace.append(row)
    
    for placements in algorithm_x(Matrix(workspace), module_count, all_placements):
        yield Solution(powergrid, placements)


def compute_best_solutions(
    selections: dict[str, list[ShipModule]],
    module_config: dict[str, ModuleConfiguration],
) -> list[Solution]:
    # something high
    highest_penalty: int = 1_000_000
    best_solutions: list[Solution] = []
    
    for solution in compute_solution(selections, module_config):
        current_penalty: int = 0
        
        for row in range(solution.height):
            for column in range(solution.width):
                cell: PowergridCellType | PlacedModule = solution.get_cell(row, column)
                
                if isinstance(cell, PlacedModule) or cell == PowergridCellType.EMPTY:
                    continue
                
                if cell == PowergridCellType.EMPTY:
                    continue
                
                if cell == PowergridCellType.UNPROTECTED:
                    current_penalty += 1
                elif cell == PowergridCellType.PROTECTED:
                    current_penalty += 2
        
        if current_penalty < highest_penalty:
            highest_penalty = current_penalty
            best_solutions.clear()
        
        if current_penalty == highest_penalty:
            best_solutions.append(solution)
    
    return best_solutions


def load_configurations() -> tuple[dict[str, HullLimitations], dict[str, ModuleConfiguration], dict[str, Colour]]:
    with open("./resources/ship-configuration.toml", "rb") as ship_configuration_file:
        config: dict[str, dict[str, int | str]] = tomllib.load(ship_configuration_file)
    
    module_configuration: dict[str, dict[str, str | int]] = config["modules"]
    
    if any(not isinstance(value, int) for value in module_configuration["colours"].values()):
        raise ValueError("all colours must be integers")
    
    module_colours: dict[str, Colour] = { }
    for module_name, colour_value in module_configuration["colours"].items():
        module_colours[module_name.replace("-", " ")] = Colour(colour_value)
    
    module_types: dict[str, ModuleType] = module_configuration["types"]
    
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
    
    return ships, module_configurations, module_colours


def adapt_selections(
    new_limitations: HullLimitations,
    previous_selection: dict[str, list[ShipModule]],
    module_config: dict[str, ModuleConfiguration],
) -> dict[str, list[ShipModule]]:
    new_selection: dict[str, list[ShipModule]] = { }
    
    for module_name, new_module_limit in new_limitations.items():
        if new_module_limit == 0:
            new_selection[module_name] = []
            continue
        
        cut_modules: list[ShipModule] = previous_selection[module_name][:new_module_limit]
        new_empty_modules: int = new_module_limit - len(cut_modules)
        
        if module_config[module_name].type == ModuleType.POWER:
            empty_module: ShipModule = EMPTY_GENERATOR
        else:
            empty_module: ShipModule = EMPTY_MODULE
        
        new_selection[module_name] = cut_modules + ([empty_module] * new_empty_modules)
    
    # print(new_selection)
    return new_selection


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
