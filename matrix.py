import copy
import os
from pathlib import Path
from typing import Sequence


class MatrixError(Exception):
    pass


class Matrix[T]:
    def __init__(self, data: Sequence[Sequence[T]]):
        if any(len(row) != len(data[0]) for row in data):
            raise MatrixError("The rows of the matrix are not the same length")
        
        self._data: tuple[tuple[T]] = tuple(tuple(row) for row in data)
    
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, Matrix):
            return False
        
        return self._data == value._data
    
    def __str__(self) -> str:
        out: str = ""
        
        for row in self._data:
            out += str(row)
            out += "\n"
        
        return out[:-1]
    
    def __repr__(self) -> str:
        return str(self)
    
    @property
    def height(self) -> int:
        return len(self._data)
    
    @property
    def width(self) -> int:
        if self.height == 0:
            return 0
        
        return len(self._data[0])
    
    def weight(self, mapping: dict[T, bool]) -> int:
        total: int = 0
        
        for row in self._data:
            if any(cell not in mapping for cell in row):
                raise MatrixError(f"unknown mapping in row {row}; mappings are {mapping}")
            
            for cell in row:
                if mapping[cell]:
                    total += 1
        
        return total
    
    def get_cell(self, row: int, column: int) -> T:
        if not (0 <= row < self.height and 0 <= column < self.width):
            raise ValueError(f"{row}x{column} is not in the matrix ({self.width}x{self.height})")
        
        return self._data[row][column]
    
    def data(self) -> list[list[T]]:
        return [list(row) for row in self._data]
    
    def transpose(self) -> Matrix[T]:
        data_out: list[list[T]] = []
        
        for x in range(self.width):
            data_out.append([self._data[y][x] for y in range(self.height)])
        
        return Matrix(data_out)
    
    def rotate_90_clockwise(self) -> Matrix[T]:
        new_data: list[list[T]] = self.transpose().data()
        
        for row in range(len(new_data)):
            new_data[row] = new_data[row][::-1]
        
        return Matrix(new_data)
    
    def map[O](self, mapping: dict[T, O]) -> Matrix[O]:
        out_matrix: list[list[O]] = []
        
        for row in self._data:
            if any(cell not in mapping for cell in row):
                raise MatrixError(f"Mapping symbol is missing for row '{row}'; mapping is {mapping}")
            
            out_matrix.append([mapping[cell] for cell in row])
        
        return Matrix(out_matrix)
    
    def copy(self) -> Matrix[T]:
        return Matrix(copy.deepcopy(self._data))
    
    def remove_row(self, row: int) -> Matrix[T]:
        data: list[list[T]] = self.data()
        
        data.pop(row)
        
        return Matrix(data)
    
    def remove_column(self, column: int) -> Matrix[T]:
        data: list[list[T]] = self.data()
        
        for row in data:
            row.pop(column)
        
        return Matrix(data)


class NamedMatrix[T](Matrix[T]):
    def __init__(self, name: str, data: Sequence[Sequence[T]]):
        super().__init__(data)
        self.name = name
    
    @classmethod
    def load_from_file(cls, file_path: os.PathLike | str) -> NamedMatrix[str]:
        file_path: Path = Path(file_path)
        
        with open(file_path) as file:
            lines = [line.strip() for line in file if line != "\n"]
        
        data: list[list[str]] = []
        
        for line in lines:
            data.append(list(line))
        
        return cls(file_path.stem.replace("-", " "), data)
    
    def copy(self) -> NamedMatrix[T]:
        return NamedMatrix(self.name, super().copy()._data)


def generate_rotations[T](matrix: Matrix[T]) -> list[Matrix[T]]:
    rotations: list[Matrix[T]] = [matrix]
    
    last_used: Matrix[T] = matrix
    for _ in range(3):
        last_used = last_used.rotate_90_clockwise()
        
        if last_used not in rotations:
            rotations.append(last_used)
    
    return rotations
