import logging
import shutil
import time
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path

import cv2 as cv
from natsort import natsorted

import utilities.utils as utils
from utilities.frames_to_text import frames_to_text
from utilities.video_to_frames import video_to_frames

logger = logging.getLogger(__name__)


class SubtitleExtractor:
    def __init__(self) -> None:
        """
        Extracts hardcoded subtitles from video.
        """
        self.video_path = None
        # Create cache directory
        self.vd_output_dir = Path(f"{Path.cwd()}/output")
        # Extracted video frame storage directory
        self.frame_output = self.vd_output_dir / "frames"
        # Extracted text file storage directory
        self.text_output = self.vd_output_dir / "extracted texts"

    @staticmethod
    def video_details(video_path: str) -> tuple:
        """
        Get the video details of the video in path.

        :return: video details
        """
        capture = cv.VideoCapture(video_path)
        fps = capture.get(cv.CAP_PROP_FPS)
        frame_total = int(capture.get(cv.CAP_PROP_FRAME_COUNT))
        frame_width = int(capture.get(cv.CAP_PROP_FRAME_WIDTH))
        frame_height = int(capture.get(cv.CAP_PROP_FRAME_HEIGHT))
        capture.release()
        return fps, frame_total, frame_width, frame_height

    @staticmethod
    def default_sub_area(frame_width, frame_height, sub_area: None | tuple) -> tuple:
        """
        Returns a default subtitle area that can be used if no subtitle is given.
        :return: Position of subtitle relative to the resolution of the video. x2 = width and y2 = height
        """
        if sub_area:
            return sub_area
        else:
            logger.debug("Subtitle area being set to default sub area")
            x1, y1, x2, y2 = 0, int(frame_height * 0.75), frame_width, frame_height
            return x1, y1, x2, y2

    def _empty_cache(self) -> None:
        """
        Delete all cache files produced during subtitle extraction.
        """
        if self.vd_output_dir.exists():
            shutil.rmtree(self.vd_output_dir)
            logger.debug("Emptying cache...")

    def _remove_duplicate_texts(self, divider: str) -> None:
        """
        Remove all texts from text output that don't have the given divider in their name.
        """
        logger.debug("Deleting duplicate texts...")
        for file in self.text_output.iterdir():
            if divider not in file.name:
                file.unlink()

    def _merge_adjacent_equal_texts(self, divider) -> None:
        """
        Merge texts that are beside each other and are the exact same.
        Use divider for duration in text name.
        """
        logger.debug("Merging adjacent equal texts")
        no_of_files = len(list(self.text_output.iterdir()))
        counter = 1
        starting_file = None
        for file1, file2 in pairwise(natsorted(self.text_output.iterdir())):
            file1_text = file1.read_text(encoding="utf-8")
            file2_text = file2.read_text(encoding="utf-8")
            counter += 1
            # print(file1.name, file2.name, file1_text, file2_text)
            if file1_text == file2_text and counter != no_of_files:
                if not starting_file:
                    starting_file = file1
            else:
                if not starting_file:  # This condition is used when the file doesn't match the previous or next file.
                    starting_file = file1
                ending_file = file1
                if counter == no_of_files:
                    ending_file = file2
                new_file_name = f"{starting_file.stem}{divider}{ending_file.stem}.txt"
                starting_file.rename(f"{starting_file.parent}/{new_file_name}")
                starting_file = None

    @staticmethod
    def similarity(text1: str, text2: str) -> float:
        return SequenceMatcher(a=text1, b=text2).quick_ratio()

    @staticmethod
    def _similar_text_name_gen(start_name: str, end_name: str, divider: str, old_divider) -> str:
        """
        Takes 2 file name durations and creates a new file name.
        """
        start_name = start_name.split(old_divider)[0]
        end_name = end_name.split(old_divider)[1]
        new_name = f"{start_name}{divider}{end_name}.txt"
        return new_name

    @staticmethod
    def _name_to_duration(name: str, divider: str) -> float:
        """
        Takes a name with two numbers and subtracts to get the duration.
        :param name: name numbers should seperated by identifier.
        :param divider: value for splitting string.
        :return: duration
        """
        name_timecode = name.split(divider)
        duration = float(name_timecode[1]) - float(name_timecode[0])
        return duration

    def _merge_adjacent_similar_texts(self, old_div, divider, similarity_threshold: float = 0.65) -> None:
        """
        Merge texts that are not the same but beside each other and similar.
        The text that has the longest duration becomes the text for all similar texts.
        :param similarity_threshold: cut off point to determine similarity.
        """
        logger.debug("Merging adjacent similar texts")
        no_of_files = len(list(self.text_output.iterdir()))
        counter = 1
        starting_file = file_text = file_duration = None
        for file1, file2 in pairwise(natsorted(self.text_output.iterdir())):
            file1_text, file1_duration = file1.read_text(encoding="utf-8"), self._name_to_duration(file1.stem, old_div)
            file2_text, file2_duration = file2.read_text(encoding="utf-8"), self._name_to_duration(file2.stem, old_div)
            similarity = self.similarity(file1_text, file2_text)
            counter += 1
            # print(f"File 1 Name: {file1.name}, Duration: {file1_duration}, Text: {file1_text}\n"
            #       f"File 2 Name: {file2.name}, Duration: {file2_duration}, Text: {file2_text}\n"
            #       f"File 1 & 2 Similarity: {similarity}\n")
            if similarity >= similarity_threshold and counter != no_of_files:
                if not starting_file:
                    starting_file = file1
                    file_text = file1_text
                    file_duration = file1_duration

                if file2_duration > file_duration:  # Change text and duration when longer duration is found.
                    file_text = file2_text
                    file_duration = file2_duration
            else:
                if not starting_file:  # This condition is used when the file doesn't match the previous or next file.
                    starting_file = file1
                    file_text = file1_text

                ending_file = file1

                new_name = self._similar_text_name_gen(starting_file.stem, ending_file.stem, divider, old_div)
                new_file_name = f"{self.text_output}/{new_name}"
                with open(new_file_name, 'w', encoding="utf-8") as text_file:
                    text_file.write(file_text)

                if counter == no_of_files:
                    new_name = file2.name.replace(old_div, divider)
                    new_file_name = f"{self.text_output}/{new_name}"
                    file_text = file2_text
                    with open(new_file_name, 'w', encoding="utf-8") as text_file:
                        text_file.write(file_text)

                starting_file = file_text = file_duration = None

    @staticmethod
    def timecode(frame_no: float) -> str:
        seconds = frame_no // 1000
        milliseconds = int(frame_no % 1000)
        minutes = 0
        hours = 0
        if seconds >= 60:
            minutes = int(seconds // 60)
            seconds = int(seconds % 60)
        if minutes >= 60:
            hours = int(minutes // 60)
            minutes = int(minutes % 60)
        smpte_token = ','
        return "%02d:%02d:%02d%s%03d" % (hours, minutes, seconds, smpte_token, milliseconds)

    def _save_subtitle(self, lines: list) -> None:
        name = self.video_path.with_suffix(".srt")
        if name.exists():
            current_time = time.strftime("%H;%M;%S")
            name = f"{name.parent}/{name.stem} {current_time} (new copy).srt"
        with open(name, 'w', encoding="utf-8") as new_sub:
            new_sub.writelines(lines)
        logger.info(f"Subtitle file generated. Name: {name}")

    def _generate_subtitle(self) -> None:
        """
        Use text files in folder to create subtitle file.
        :return:
        """
        # cancel if process has been cancelled by gui.
        if utils.process_state():
            logger.warning("Subtitle generation process interrupted!")
            return

        logger.info("Generating subtitle...")
        self._merge_adjacent_equal_texts("--")
        self._remove_duplicate_texts("--")
        self._merge_adjacent_similar_texts("--", "---")
        self._remove_duplicate_texts("---")
        subtitles = []
        line_code = 0
        for file in natsorted(self.text_output.iterdir()):
            file_name = file.stem.split("---")
            line_code += 1
            frame_start = self.timecode(float(file_name[0]))
            frame_end = self.timecode(float(file_name[1]))
            file_content = file.read_text(encoding="utf-8")
            subtitle_line = f"{line_code}\n{frame_start} --> {frame_end}\n{file_content}\n\n"
            subtitles.append(subtitle_line)
        self._save_subtitle(subtitles)
        logger.info("Subtitle generated!")

    def run(self, video_path: str, sub_area: tuple = None) -> None:
        """
        Run through the steps of extracting texts from subtitle area in video to create subtitle.
        """
        start = cv.getTickCount()
        # Empty cache at the beginning of program run before it recreates itself.
        self._empty_cache()
        # If the directory does not exist, create the folder.
        if not self.frame_output.exists():
            self.frame_output.mkdir(parents=True)
        if not self.text_output.exists():
            self.text_output.mkdir(parents=True)

        self.video_path = Path(video_path)

        fps, frame_total, frame_width, frame_height = self.video_details(video_path)
        sub_area = self.default_sub_area(frame_width, frame_height, sub_area)

        logger.info(f"File Path: {self.video_path}")
        logger.info(f"Frame Total: {frame_total}, Frame Rate: {fps}")
        logger.info(f"Resolution: {frame_width} X {frame_height}")
        logger.info(f"Subtitle Area: {sub_area}")

        video_to_frames(self.video_path, self.frame_output, sub_area)
        frames_to_text(self.frame_output, self.text_output)
        self._generate_subtitle()

        end = cv.getTickCount()
        total_time = (end - start) / cv.getTickFrequency()
        logger.info(f"Subtitle Extraction Done! Total time: {round(total_time, 3)}s\n")
        self._empty_cache()


if __name__ == '__main__':
    from utilities.logger_setup import get_logger

    get_logger()

    logger.debug("\n\nMain program Started.")
    test_video = Path(r"")
    se = SubtitleExtractor()
    se.run(str(test_video))
    logger.debug("Main program Ended.\n\n")
