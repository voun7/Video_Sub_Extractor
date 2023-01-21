import logging
from configparser import ConfigParser
from pathlib import Path

logger = logging.getLogger(__name__)


class Process:
    interrupt_process = False

    @classmethod
    def start_process(cls) -> None:
        """
        Allows process to run.
        """
        cls.interrupt_process = False
        logger.debug(f"interrupt_process set to: {cls.interrupt_process}")

    @classmethod
    def stop_process(cls) -> None:
        """
        Stops process from running.
        """
        cls.interrupt_process = True
        logger.debug(f"interrupt_process set to: {cls.interrupt_process}")


class Config:
    config_file = Path("utilities/config.ini")
    config = ConfigParser()
    config.read(config_file)

    sections = ["Frame Extraction", "Text Extraction", "Subtitle Generator"]
    keys = ["frame_extraction_frequency", "frame_extraction_chunk_size", "text_extraction_chunk_size",
            "ocr_max_processes", "ocr_rec_language", "text_similarity_threshold"]

    # Default values
    default_frame_extraction_frequency = 2
    default_frame_extraction_chunk_size = 250
    default_text_extraction_chunk_size = 150
    default_ocr_max_processes = 4
    default_ocr_rec_language = "ch"
    default_text_similarity_threshold = 0.65

    # Initial values
    frame_extraction_frequency = frame_extraction_chunk_size = None
    text_extraction_chunk_size = ocr_max_processes = ocr_rec_language = None
    text_similarity_threshold = None

    def __init__(self) -> None:
        if not self.config_file.exists():
            self.create_default_config_file()
        self.load_config()

    def create_default_config_file(self) -> None:
        self.config[self.sections[0]] = {self.keys[0]: str(self.default_frame_extraction_frequency),
                                         self.keys[1]: self.default_frame_extraction_chunk_size}
        self.config[self.sections[1]] = {self.keys[2]: self.default_text_extraction_chunk_size,
                                         self.keys[3]: self.default_ocr_max_processes,
                                         self.keys[4]: self.default_ocr_rec_language}
        self.config[self.sections[2]] = {self.keys[5]: str(self.default_text_similarity_threshold)}
        with open(self.config_file, 'w') as configfile:
            self.config.write(configfile)

    @classmethod
    def load_config(cls) -> None:
        cls.frame_extraction_frequency = int(cls.config[cls.sections[0]][cls.keys[0]])
        cls.frame_extraction_chunk_size = int(cls.config[cls.sections[0]][cls.keys[1]])
        cls.text_extraction_chunk_size = int(cls.config[cls.sections[1]][cls.keys[2]])
        cls.ocr_max_processes = int(cls.config[cls.sections[1]][cls.keys[3]])
        cls.ocr_rec_language = cls.config[cls.sections[1]][cls.keys[4]]
        cls.text_similarity_threshold = float(cls.config[cls.sections[2]][cls.keys[5]])

    @classmethod
    def set_config(cls, **kwargs):
        # Write into memory & file
        cls.frame_extraction_frequency = kwargs.get("frame_extraction_frequency", cls.frame_extraction_frequency)
        cls.config[cls.sections[0]][cls.keys[0]] = str(cls.frame_extraction_frequency)
        cls.frame_extraction_chunk_size = kwargs.get("frame_extraction_chunk_size", cls.frame_extraction_chunk_size)
        cls.config[cls.sections[0]][cls.keys[1]] = str(cls.frame_extraction_chunk_size)

        cls.text_extraction_chunk_size = kwargs.get("text_extraction_chunk_size", cls.text_extraction_chunk_size)
        cls.config[cls.sections[1]][cls.keys[2]] = str(cls.text_extraction_chunk_size)
        cls.ocr_max_processes = kwargs.get("ocr_max_processes", cls.ocr_max_processes)
        cls.config[cls.sections[1]][cls.keys[3]] = str(cls.ocr_max_processes)
        cls.ocr_rec_language = kwargs.get("ocr_rec_language", cls.ocr_rec_language)
        cls.config[cls.sections[1]][cls.keys[4]] = cls.ocr_rec_language

        cls.text_similarity_threshold = kwargs.get("text_similarity_threshold", cls.text_similarity_threshold)
        cls.config[cls.sections[2]][cls.keys[5]] = str(cls.text_similarity_threshold)

        with open(cls.config_file, 'w') as configfile:
            cls.config.write(configfile)
        logger.debug("Configuration values changed!")


def print_progress(iteration, total, prefix='', suffix='', decimals=3, bar_length=25):
    """
    Call in a loop to create standard out progress bar
    :param iteration: current iteration
    :param total: total iterations
    :param prefix: prefix string
    :param suffix: suffix string
    :param decimals: positive number of decimals in percent complete
    :param bar_length: character length of bar
    :return: None
    """

    format_str = "{0:." + str(decimals) + "f}"  # format the % done number string
    percents = format_str.format(100 * (iteration / float(total)))  # calculate the % done
    filled_length = int(round(bar_length * iteration / float(total)))  # calculate the filled bar length
    bar = '#' * filled_length + '-' * (bar_length - filled_length)  # generate the bar string
    # print(f"\r{prefix} |{bar}| {percents}% {suffix}", end='', flush=True)  # prints progress on the same line
    logger.info(f"{prefix} |{bar}| {percents}% {suffix}")


if __name__ == '__main__':
    pass
else:
    Config()
