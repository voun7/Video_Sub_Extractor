import logging
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import utilities.utils as utils
from custom_paddleocr import PaddleOCR

logger = logging.getLogger(__name__)

paddle_ocr = PaddleOCR(
    det_model_dir=f"{Path(__file__).parent.parent}/models/{utils.Config.ocr_rec_language}/det",
    rec_model_dir=f"{Path(__file__).parent.parent}/models/{utils.Config.ocr_rec_language}/rec",
    cls_model_dir=f"{Path(__file__).parent.parent}/models/{utils.Config.ocr_rec_language}/cls",
    use_angle_cls=True,
    lang=utils.Config.ocr_rec_language,
    show_log=False
)


def extract_bboxes(files: Path, drop_score: float = 0.9) -> list:
    """
    Returns the bounding boxes of detected texted in images.
    :param files: Directory with images for detection.
    :param drop_score: Filter the results by score and those results below this score will not be returned.
    """
    boxes = []
    for file in files.iterdir():
        result = paddle_ocr.ocr(str(file))
        result = result[0]
        if result:
            score = result[0][1][1]
            if score > drop_score:
                box = result[0][0]
                boxes.append(box)
    return boxes


def extract_text(text_output: Path, files: list) -> int:
    """
    Extract text from a frame using paddle ocr
    :param text_output: directory for extracted texts
    :param files: files with text for extraction
    :return: count of texts extracted
    """
    saved_count = 0
    for file in files:
        result = paddle_ocr.ocr(str(file))
        result = result[0]
        if result:
            text_list = [line[1][0] for line in result]
            text = " ".join(text_list)
            name = Path(f"{text_output}/{file.stem}.txt")
            with open(name, 'w', encoding="utf-8") as text_file:
                text_file.write(text)
        saved_count += 1
    return saved_count


def frames_to_text(frame_output: Path, text_output: Path) -> None:
    """
    Extracts the texts from frames using multiprocessing
    :param frame_output: directory of the frames
    :param text_output: directory for extracted texts
    """
    # Size of files given to each processor.
    chunk_size = utils.Config.text_extraction_chunk_size
    # Number of processors to be used.
    ocr_max_processes = utils.Config.ocr_max_processes
    # Cancel if process has been cancelled by gui.
    if utils.Process.interrupt_process:
        logger.warning("Text extraction process interrupted!")
        return

    logger.info("Starting to extracting text from frames...")

    files = [file for file in frame_output.iterdir()]
    file_chunks = [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]

    prefix = "Extracting text from frames"
    logger.debug("Using multiprocessing for extracting text")

    with ProcessPoolExecutor(max_workers=ocr_max_processes) as executor:
        futures = [executor.submit(extract_text, text_output, files) for files in file_chunks]
        for i, f in enumerate(as_completed(futures)):  # as each  process completes
            error = f.exception()
            if error:
                logger.exception(f.result())
                logger.exception(error)
            # print it's progress
            utils.print_progress(i, len(file_chunks) - 1, prefix)
    logger.info("Text Extractions Done!")
