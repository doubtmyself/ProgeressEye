import hashlib
from typing import Any, Dict, TypeVar, Callable, Optional
from PIL import Image

T = TypeVar("T")

class ImageCacheMixin:
    """이미지 기반 분석 결과 캐싱을 제공하는 믹스인 클래스.
    
    분석기의 특성에 따라 정밀도(원본 비교) 또는 성능(리사이징 비교)을 선택할 수 있다.
    """

    def __init__(self) -> None:
        self._prev_hashes: Dict[str, str] = {}
        self._prev_results: Dict[str, Any] = {}

    def _get_image_data_for_hash(self, image: Image.Image) -> bytes:
        """해시 계산에 사용할 이미지 데이터를 반환한다.
        
        기본값은 원본 이미지의 바이트 데이터(가장 정밀함)이다.
        정밀도보다 성능이 중요하거나 미세 노이즈를 무시해야 하는 경우 
        하위 클래스에서 이 메서드를 오버라이드하여 리사이징된 데이터를 반환하게 할 수 있다.
        """
        return image.tobytes()

    def _compute_image_hash(self, image: Image.Image) -> str:
        """이미지의 MD5 해시값을 계산한다."""
        data = self._get_image_data_for_hash(image)
        return hashlib.md5(data).hexdigest()

    def get_cached_or_compute(
        self, 
        region_id: str, 
        image: Image.Image, 
        compute_func: Callable[..., T], 
        *args, 
        **kwargs
    ) -> T:
        """캐시된 결과가 있으면 반환하고, 없으면 계산 후 저장한다."""
        if not region_id:
            return compute_func(image, *args, **kwargs)

        img_hash = self._compute_image_hash(image)
        
        if self._prev_hashes.get(region_id) == img_hash:
            return self._prev_results.get(region_id)
        
        # 실제 계산 수행
        result = compute_func(image, *args, **kwargs)
        
        # 캐시 업데이트
        self._prev_hashes[region_id] = img_hash
        self._prev_results[region_id] = result
        
        return result

    def clear_cache(self, region_id: Optional[str] = None) -> None:
        """특정 영역 또는 전체 캐시를 초기화한다."""
        if region_id:
            self._prev_hashes.pop(region_id, None)
            self._prev_results.pop(region_id, None)
        else:
            self._prev_hashes.clear()
            self._prev_results.clear()
