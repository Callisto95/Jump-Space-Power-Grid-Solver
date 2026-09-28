import copy
from typing import Generator

from matrix import Matrix


def algorithm_x_recursive[T](
    workspace: Matrix[int],
    primary_column_count: int,
    row_labels: list[T],
    previous_solution: list[T],
) -> Generator[list[T]]:
    
    if primary_column_count == 0:
        yield previous_solution
        return
    
    if workspace.height == 0:
        return  # dead end
    
    transposed_workspace: Matrix[int] = workspace.transpose()
    
    column_counts: list[int] = [sum(column) for column in transposed_workspace.data[:primary_column_count]]
    lowest_column_count: int = min(column_counts)
    
    if lowest_column_count == 0:
        print("no solution")
        return  # dead end, backtrack
    
    selected_column_index: int = column_counts.index(lowest_column_count)
    row_candidate_indices: list[int] = [
        index
        for index, cell in enumerate(transposed_workspace.data[selected_column_index])
        if cell == 1
    ]
    
    # step 4, split
    for row_candidate_index in row_candidate_indices:
        current_row_labels: list[T] = copy.deepcopy(row_labels)
        current_solution: list[T] = copy.deepcopy(previous_solution)
        current_workspace: Matrix[int] = workspace.copy()
        current_transposed_workspace: Matrix[int] = transposed_workspace.copy()
        
        current_solution.append(current_row_labels[row_candidate_index])
        
        to_remove_column_indices: set[int] = set()
        for column_index, cell in enumerate(current_workspace.data[row_candidate_index]):
            if cell == 0:
                continue
            
            to_remove_column_indices.add(column_index)
        
        to_remove_row_indices: set[int] = set()
        for column_index in to_remove_column_indices:
            for row_index, cell in enumerate(current_transposed_workspace.data[column_index]):
                if cell == 0:
                    continue
                
                to_remove_row_indices.add(row_index)
        
        # reverse removal to keep indices correct
        for row_index in sorted(to_remove_row_indices, reverse=True):
            current_workspace.data.pop(row_index)
            current_row_labels.pop(row_index)
        
        for column_index in sorted(to_remove_column_indices, reverse=True):
            for row in current_workspace.data:
                row.pop(column_index)
        
        removed_primary_columns: int = len(
            list(filter(lambda index: index < primary_column_count, to_remove_column_indices)),
        )
        
        yield from algorithm_x_recursive(
            current_workspace,
            primary_column_count - removed_primary_columns,
            current_row_labels,
            current_solution,
        )


def algorithm_x[T](
    workspace: Matrix[int],
    primary_column_count: int,  # number of modules
    row_labels: list[T],
) -> Generator[list[T]]:
    if len(row_labels) != workspace.height:
        raise ValueError(
            f"the number of row labels ({len(row_labels)}) and the height of the matrix ({workspace.height}) must "
            f"match",
        )
    
    return algorithm_x_recursive(workspace, primary_column_count, row_labels, [])


__all__ = ["algorithm_x"]
