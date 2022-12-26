import logging
import shutil
from concurrent.futures import ProcessPoolExecutor, as_completed
from difflib import SequenceMatcher
from itertools import pairwise
from pathlib import Path

import cv2 as cv
import numpy as np
from natsort import natsorted
from tqdm import tqdm

from logger_setup import get_log
from paddleocr import PaddleOCR

logger = logging.getLogger(__name__)


class SubtitleExtractor:
    ocr = PaddleOCR(use_angle_cls=True, lang='ch', show_log=False)

    def __init__(self, extract_frequency: int = 2, frame_chunk_size: int = 250, ocr_chunk_size: int = 150,
                 ocr_max_processes: int = 4,
                 text_similarity_threshold: float = 0.8) -> None:
        """
        Extracts hardcoded subtitles from video.

        :param extract_frequency: extract every this many frames
        :param frame_chunk_size: how many frames to split into chunks (one chunk per cpu core process)
        :param ocr_chunk_size:
        :param ocr_max_processes:
        :param text_similarity_threshold:
        """
        self.extract_frequency = extract_frequency
        self.frame_chunk_size = frame_chunk_size
        self.ocr_chunk_size = ocr_chunk_size
        self.ocr_max_processes = ocr_max_processes
        self.text_similarity_threshold = text_similarity_threshold
        self.video_path = None
        self.video_details = None
        self.sub_area = None
        # Create cache directory
        self.vd_output_dir = Path(f"{Path.cwd()}/output")
        # Extracted video frame storage directory
        self.frame_output = self.vd_output_dir / "frames"
        # Extracted text file storage directory
        self.text_output = self.vd_output_dir / "extracted texts"

    def get_video_details(self) -> tuple:
        if "mp4" not in self.video_path.suffix:
            logger.error("File path does not contain video!")
            exit()
        capture = cv.VideoCapture(str(self.video_path))
        fps = capture.get(cv.CAP_PROP_FPS)
        frame_count = int(capture.get(cv.CAP_PROP_FRAME_COUNT))
        frame_height = int(capture.get(cv.CAP_PROP_FRAME_HEIGHT))
        frame_width = int(capture.get(cv.CAP_PROP_FRAME_WIDTH))
        capture.release()
        return fps, frame_count, frame_height, frame_width

    def __subtitle_area(self, sub_area: None | tuple) -> tuple:
        """
        Returns a default subtitle area that can be used if no subtitle is given.
        :return: Position of subtitle relative to the resolution of the video. x2 = width and y2 = height
        """
        if sub_area:
            return sub_area
        else:
            _, _, frame_height, frame_width = self.video_details
            x1, y1, x2, y2 = 0, int(frame_height * 0.75), frame_width, frame_height
            return x1, y1, x2, y2

    @staticmethod
    def rescale_frame(frame: np.ndarray, scale: float = 0.5) -> np.ndarray:
        height = int(frame.shape[0] * scale)
        width = int(frame.shape[1] * scale)
        dimensions = (width, height)
        return cv.resize(frame, dimensions, interpolation=cv.INTER_AREA)

    def view_frames(self) -> None:
        video_cap = cv.VideoCapture(str(self.video_path))
        while True:
            success, frame = video_cap.read()
            if not success:
                logger.warning(f"Video has ended!")  # or failed to read
                break
            x1, y1, x2, y2 = self.sub_area
            # draw rectangle over subtitle area
            top_left_corner = (x1, y1)
            bottom_right_corner = (x2, y2)
            color_red = (0, 0, 255)
            cv.rectangle(frame, top_left_corner, bottom_right_corner, color_red, 2)

            # show preprocessed subtitle area
            preprocessed_sub = self.preprocess_sub_frame(frame)
            cv.imshow("Preprocessed Sub", preprocessed_sub)

            frame_resized = self.rescale_frame(frame)
            cv.imshow("Video Output", frame_resized)

            if cv.waitKey(1) == ord('q'):
                break
        video_cap.release()
        cv.destroyAllWindows()

    def empty_cache(self) -> None:
        """
        Delete all cache files produced during subtitle extraction.
        """
        if self.vd_output_dir.exists():
            shutil.rmtree(self.vd_output_dir)
            logger.debug("Emptying cache...")

    def preprocess_sub_frame(self, frame: np.ndarray) -> np.ndarray:
        x1, y1, x2, y2 = self.sub_area
        subtitle_area = frame[y1:y2, x1:x2]  # crop the subtitle area
        # rescaled_sub_area = self.rescale_frame(subtitle_area)
        # gray_image = cv.cvtColor(rescaled_sub_area, cv.COLOR_BGR2GRAY)
        return subtitle_area

    def extract_frames(self, start: int, end: int) -> int:
        """
        Extract frames from a video using OpenCVs VideoCapture.

        :param start: start frame
        :param end: end frame
        :return: count of images saved
        """

        capture = cv.VideoCapture(str(self.video_path))  # open the video using OpenCV

        if start < 0:  # if start isn't specified lets assume 0
            start = 0
        if end < 0:  # if end isn't specified assume the end of the video
            end = int(capture.get(cv.CAP_PROP_FRAME_COUNT))

        capture.set(1, start)  # set the starting frame of the capture
        frame = start  # keep track of which frame we are up to, starting from start
        while_safety = 0  # a safety counter to ensure we don't enter an infinite while loop
        saved_count = 0  # a count of how many frames we have saved

        while frame < end:  # let's loop through the frames until the end

            _, image = capture.read()  # read an image from the capture

            if while_safety > 500:  # break the while if our safety max out at 500
                break

            # sometimes OpenCV reads Nones during a video, in which case we want to just skip
            if image is None:  # if we get a bad return flag or the image we read is None, lets not save
                while_safety += 1  # add 1 to our while safety, since we skip before incrementing our frame variable
                continue  # skip

            if frame % self.extract_frequency == 0:  # if this is a frame we want to write out
                while_safety = 0  # reset the safety count
                frame_position = capture.get(cv.CAP_PROP_POS_MSEC)  # get the name of the frame
                file_name = Path(f"{self.frame_output}/{frame_position}.jpg")  # create the file save path and format
                preprocessed_frame = self.preprocess_sub_frame(image)
                cv.imwrite(str(file_name), preprocessed_frame)  # save the extracted image
                saved_count += 1  # increment our counter by one

            frame += 1  # increment our frame count

        capture.release()  # after the while has finished close the capture
        return saved_count  # and return the count of the images we saved

    def video_to_frames(self) -> None:
        """
        Extracts the frames from a video using multiprocessing.
        """

        frame_count = self.video_details[1]

        # ignore chunk size if it's greater than frame count
        self.frame_chunk_size = self.frame_chunk_size if frame_count > self.frame_chunk_size else frame_count - 1

        if frame_count < 1:  # if video has no frames, might be and opencv error
            logger.error("Video has no frames. Check your OpenCV installation")

        # split the frames into chunk lists
        frame_chunks = [[i, i + self.frame_chunk_size] for i in range(0, frame_count, self.frame_chunk_size)]
        # make sure last chunk has correct end frame, also handles case chunk_size < frame count
        frame_chunks[-1][-1] = min(frame_chunks[-1][-1], frame_count - 1)
        logger.debug(f"Frame chunks = {frame_chunks}")

        prefix = "Extracting frames from video chunks"
        logger.debug("Using multiprocessing for extracting frames")
        # execute across multiple cpu cores to speed up processing, get the count automatically
        with ProcessPoolExecutor() as executor:
            futures = [executor.submit(self.extract_frames, f[0], f[1]) for f in frame_chunks]
            pbar = tqdm(total=len(frame_chunks), desc=prefix, colour="green")
            for f in as_completed(futures):  # as each process completes
                error = f.exception()
                if error:
                    logger.exception(error)
                pbar.update()
            pbar.close()
        logger.info("Done extracting frames from video!")

    def extract_text(self, files: list) -> int:
        saved_count = 0
        for file in files:
            saved_count += 1
            name = Path(f"{self.text_output}/{file.stem}.txt")
            result = self.ocr.ocr(str(file), cls=True)
            if result[0]:
                text = result[0][0][1][0]
                with open(name, 'w', encoding="utf-8") as text_file:
                    text_file.write(text)
        return saved_count

    def frames_to_text(self) -> None:
        files = [file for file in self.frame_output.iterdir()]
        file_chunks = [files[i:i + self.ocr_chunk_size] for i in range(0, len(files), self.ocr_chunk_size)]

        prefix = "Extracting text from frame chunks"
        logger.debug("Using multiprocessing for extracting text")
        with ProcessPoolExecutor(max_workers=self.ocr_max_processes) as executor:
            futures = [executor.submit(self.extract_text, files) for files in file_chunks]
            pbar = tqdm(total=len(file_chunks), desc=prefix, colour="green")
            for f in as_completed(futures):
                error = f.exception()
                if error:
                    logger.exception(error)
                pbar.update()
            pbar.close()
        logger.info("Done extracting texts!")

    @staticmethod
    def similarity(text1: str, text2: str) -> float:
        return SequenceMatcher(a=text1, b=text2).quick_ratio()

    def remove_duplicate_texts(self) -> None:
        logger.info("Deleting duplicate texts...")
        for file in self.text_output.iterdir():
            if "--" not in file.name:
                file.unlink()

    def merge_similar_texts(self) -> None:
        no_of_files = len(list(self.text_output.iterdir())) - 1
        counter = 0
        starting_file = None
        for file1, file2 in pairwise(natsorted(self.text_output.iterdir())):
            similarity = self.similarity(file1.read_text(encoding="utf-8"), file2.read_text(encoding="utf-8"))
            counter += 1
            if similarity > self.text_similarity_threshold and counter != no_of_files:
                # print(file1.name, file2.name, similarity)
                if not starting_file:
                    starting_file = file1
            else:
                # print(file1.name, file2.name, similarity)
                if not starting_file:
                    starting_file = file1
                ending_file = file1
                if starting_file == ending_file:
                    ending_file = file2
                new_file_name = f"{starting_file.stem}--{ending_file.stem}.txt"
                starting_file.rename(f"{starting_file.parent}/{new_file_name}")
                starting_file = None

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
            name = f"{name.parent}/{name.stem} (new copy).srt"
        logger.info(f"Subtitle file successfully generated. Name: {name}")
        with open(name, 'w', encoding="utf-8") as new_sub:
            new_sub.writelines(lines)

    def generate_subtitle(self) -> None:
        self.merge_similar_texts()
        self.remove_duplicate_texts()
        subtitles = []
        line_code = 0
        for file in natsorted(self.text_output.iterdir()):
            file_name = file.stem.split("--")
            line_code += 1
            frame_start = self.timecode(float(file_name[0]))
            frame_end = self.timecode(float(file_name[1]))
            file_content = file.read_text(encoding="utf-8")
            subtitle_line = f"{line_code}\n{frame_start} --> {frame_end}\n{file_content}\n\n"
            subtitles.append(subtitle_line)
        self._save_subtitle(subtitles)
        logger.info("Subtitle generated!")

    def run(self, video_path: Path, sub_area: tuple = None) -> None:
        """
        Run through the steps of extracting video.
        """
        start = cv.getTickCount()
        # Empty cache at the beginning of program run before it recreates itself
        self.empty_cache()
        # If the directory does not exist, create the folder
        if not self.frame_output.exists():
            self.frame_output.mkdir(parents=True)
        if not self.text_output.exists():
            self.text_output.mkdir(parents=True)
        self.video_path = video_path
        self.video_details = self.get_video_details()
        self.sub_area = self.__subtitle_area(sub_area)

        fps, frame_count, frame_height, frame_width = self.video_details
        logger.info(f"File Path: {self.video_path}")
        logger.info(f"Frame Count: {frame_count}, Frame Rate: {fps}")
        logger.info(f"Resolution: {frame_width} X {frame_height}")
        logger.info(f"Subtitle Area: {self.sub_area}")

        # self.view_frames()
        logger.info("Starting to extracting video keyframes...")
        self.video_to_frames()
        logger.info("Starting to extracting text from frames...")
        self.frames_to_text()
        logger.info("Generating subtitle...")
        self.generate_subtitle()

        end = cv.getTickCount()
        total_time = (end - start) / cv.getTickFrequency()
        logger.info(f"Subtitle file generated successfully, Total time: {round(total_time, 3)}s\n")
        self.empty_cache()


if __name__ == '__main__':
    get_log()
    logger.debug("Logging Started")
    test_videos = Path(r"C:\Users\VOUN-XPS\Downloads\test videos")
    se = SubtitleExtractor()
    for video in test_videos.glob("*.mp4"):
        se.run(video)

    logger.debug("Logging Ended\n\n")
