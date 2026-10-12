"""Decode bounded raster uploads and publish only normalized PNG bytes."""
import io
import re
import uuid
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_IMAGE_DIMENSION = 4096
MAX_IMAGE_PIXELS = 16_000_000
IMAGE_NAME = re.compile(r'^seo_public/([a-f0-9]{32})\.png$')


def image_path(name):
    match = IMAGE_NAME.fullmatch(name or '')
    return '/seo-images/' + str(uuid.UUID(hex=match.group(1))) + '/' if match else ''


def image_upload_to(instance, filename):
    return 'seo_public/' + uuid.uuid4().hex + '.png'


def normalize_image(upload):
    if getattr(upload, '_seo_normalized', False):
        return upload, upload._seo_dimensions
    if upload.size > MAX_IMAGE_BYTES:
        raise ValidationError('이미지는 5MB 이하로 업로드하세요.')
    try:
        upload.seek(0)
        data = upload.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValidationError('이미지는 5MB 이하로 업로드하세요.')
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=['PNG', 'JPEG', 'WEBP']) as source:
                if source.format not in {'JPEG', 'PNG', 'WEBP'} or getattr(source, 'is_animated', False):
                    raise ValidationError('정적인 PNG·JPEG·WebP 이미지만 업로드할 수 있습니다.')
                width, height = source.size
                if width < 1 or height < 1 or max(width, height) > MAX_IMAGE_DIMENSION or width * height > MAX_IMAGE_PIXELS:
                    raise ValidationError('이미지는 가로·세로 4096px 이하, 총 1,600만 픽셀 이하로 업로드하세요.')
                source.verify()
            with Image.open(io.BytesIO(data), formats=['PNG', 'JPEG', 'WEBP']) as source:
                source.load()
                image = ImageOps.exif_transpose(source)
                mode = 'RGBA' if 'A' in image.getbands() or 'transparency' in image.info else 'RGB'
                pixels = image.convert(mode)
                # A fresh image excludes EXIF, text chunks, ICC profiles and source metadata.
                clean = Image.new(mode, pixels.size)
                clean.paste(pixels)
                output = io.BytesIO()
                clean.save(output, format='PNG')
                dimensions = clean.size
                if output.tell() > MAX_IMAGE_BYTES:
                    raise ValidationError('PNG로 변환한 이미지가 5MB를 초과합니다. 크기나 해상도를 줄여 업로드하세요.')
        normalized = ContentFile(output.getvalue(), name=uuid.uuid4().hex + '.png')
        normalized._seo_normalized = True
        normalized._seo_dimensions = dimensions
        return normalized, dimensions
    except ValidationError:
        raise
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ValidationError('올바른 PNG·JPEG·WebP 이미지 파일을 업로드하세요.') from exc
    finally:
        upload.seek(0)


def stored_dimensions(file):
    try:
        with file.open('rb') as source:
            with Image.open(source, formats=['PNG']) as image:
                return image.size
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValidationError('저장된 공유 이미지를 읽을 수 없습니다. 이미지를 다시 업로드하거나 삭제하세요.') from exc
