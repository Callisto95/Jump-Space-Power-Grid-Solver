import questionary
from questionary import Choice

from game import (
    adapt_selections,
    compute_solution,
    EMPTY_GENERATOR,
    EMPTY_MODULE,
    HullLimitations,
    initialize_selections,
    load_configurations,
    ModuleConfiguration,
    ModuleType,
    PlacedModule, PowergridCellType, ShipModule,
)


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
                # for module in solution.modules:
                #     print(module.module.name, "@", module.position)
                #     print(module.matrix)
                # print("-" * 50)
                
                for row in range(solution.powergrid.height):
                    for column in range(solution.powergrid.width):
                        cell: PowergridCellType | PlacedModule = solution.get_cell(row, column)
                        if isinstance(cell, PowergridCellType):
                            name = cell.name[:1]
                        else:
                            name = cell.module.name[:1]
                        print(name, end="")
                    print()
                
                print("=" * 50)
                
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
