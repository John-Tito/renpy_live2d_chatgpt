init -1 python:
    import os
    from collections import defaultdict

    class CharacterPreprocessor:
        def __init__(self, character_name):
            ## exp
            self.exps = sorted(self.__parse_file(character_name, 'exp'))

            ## motions
            self.motions = sorted(self.__parse_file(character_name, 'motions'))

        def __parse_file(self, character_name, tag):
            directory_path = os.path.join(config.gamedir, character_name, tag)

            result = []

            for dirpath, dirnames, filenames in os.walk(directory_path):
                for file in filenames:
                    file = file.split('.')[0]
                    file = file.lower()
                    result.append(file)

            return result