import copy
import os
from pathlib import Path


class MatrixError(Exception):
    pass


class Matrix[T]:
    def __init__(self, data: list[list[T]]):
        if any(len(row) != len(data[0]) for row in data):
            raise MatrixError("The rows of the matrix are not the same length")
        
        self.data: list[list[T]] = data
    
    def __eq__(self, value: object, /) -> bool:
        if not isinstance(value, Matrix):
            return False
        
        return self.data == value.data
    
    def __str__(self) -> str:
        out: str = ""
        
        for row in self.data:
            out += str(row)
            out += "\n"
        
        return out[:-1]
    
    def __repr__(self) -> str:
        return str(self)
    
    @property
    def height(self) -> int:
        return len(self.data)
    
    @property
    def width(self) -> int:
        if self.height == 0:
            return 0
        
        return len(self.data[0])
    
    def weight(self, mapping: dict[T, bool]) -> int:
        total: int = 0
        
        for row in self.data:
            if any(cell not in mapping for cell in row):
                raise MatrixError(f"unknown mapping in row {row}; mappings are {mapping}")
            
            for cell in row:
                if mapping[cell]:
                    total += 1
        
        return total
    
    def transpose(self) -> Matrix[T]:
        data_out: list[list[T]] = []
        
        for x in range(self.width):
            data_out.append([self.data[y][x] for y in range(self.height)])
        
        return Matrix(data_out)
    
    def rotate_90_clockwise(self) -> Matrix[T]:
        matrix_out = self.transpose()
        
        for row in range(matrix_out.height):
            matrix_out.data[row] = matrix_out.data[row][::-1]
        
        return matrix_out
    
    def map[O](self, mapping: dict[T, O]) -> Matrix[O]:
        out_matrix: list[list[O]] = []
        
        for row in self.data:
            if any(cell not in mapping for cell in row):
                raise MatrixError(f"Mapping symbol is missing for row '{row}'; mapping is {mapping}")
            
            out_matrix.append([mapping[cell] for cell in row])
        
        return Matrix(out_matrix)
    
    def copy(self) -> Matrix[T]:
        return Matrix(copy.deepcopy(self.data))


class NamedMatrix[T](Matrix[T]):
    def __init__(self, name: str, data: list[list[T]]):
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
        return NamedMatrix(self.name, super().copy().data)


def generate_rotations[T](matrix: Matrix[T]) -> list[Matrix[T]]:
    rotations: list[Matrix[T]] = [matrix]
    
    last_used: Matrix[T] = matrix
    for _ in range(3):
        last_used = last_used.rotate_90_clockwise()
        
        if last_used not in rotations:
            rotations.append(last_used)
    
    return rotations
