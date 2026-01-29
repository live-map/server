"""
PostMedia Service - Business logic for media attachments.

Handles S3 uploads and media metadata management.
"""

import logging
import uuid
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.post.media.repository import PostMediaRepository
from app.models.post_media import MediaType, PostMedia

logger = logging.getLogger(__name__)


class PostMediaService:
    """
    PostMedia 관련 비즈니스 로직을 처리하는 서비스.

    S3 업로드와 미디어 메타데이터 관리를 담당합니다.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.media_repo = PostMediaRepository(session)

    async def add_media_to_post(
        self,
        post_id: uuid.UUID,
        media_type: MediaType,
        url: str,
        thumbnail_url: str | None = None,
        original_filename: str | None = None,
        file_size: int | None = None,
        duration: int | None = None,
        width: int | None = None,
        height: int | None = None,
        order: int = 0,
    ) -> PostMedia:
        """
        게시글에 미디어 추가.

        S3 업로드 후 호출하여 메타데이터를 저장합니다.

        Args:
            post_id: 게시글 UUID
            media_type: IMAGE 또는 VIDEO
            url: S3/CloudFront URL
            thumbnail_url: 비디오 썸네일 URL (선택)
            original_filename: 원본 파일명 (선택)
            file_size: 파일 크기 bytes (선택)
            duration: 비디오 길이 초 (선택)
            width: 너비 pixels (선택)
            height: 높이 pixels (선택)
            order: 표시 순서 (기본 0)

        Returns:
            생성된 PostMedia
        """
        media = PostMedia(
            post_id=post_id,
            media_type=media_type,
            url=url,
            thumbnail_url=thumbnail_url,
            original_filename=original_filename,
            file_size=file_size,
            duration=duration,
            width=width,
            height=height,
            order=order,
        )
        created = await self.media_repo.create(media)
        await self.session.commit()
        logger.info(f"Added {media_type.value} to post {post_id}: {created.id}")
        return created

    async def add_multiple_media_to_post(
        self,
        post_id: uuid.UUID,
        media_data_list: list[dict],
    ) -> list[PostMedia]:
        """
        게시글에 여러 미디어 일괄 추가.

        Args:
            post_id: 게시글 UUID
            media_data_list: 미디어 데이터 목록
                각 항목: {
                    "media_type": MediaType,
                    "url": str,
                    "thumbnail_url": str | None,
                    "original_filename": str | None,
                    "file_size": int | None,
                    "duration": int | None,
                    "width": int | None,
                    "height": int | None,
                    "order": int,
                }

        Returns:
            생성된 PostMedia 목록
        """
        media_list = []
        for idx, data in enumerate(media_data_list):
            media = PostMedia(
                post_id=post_id,
                media_type=data["media_type"],
                url=data["url"],
                thumbnail_url=data.get("thumbnail_url"),
                original_filename=data.get("original_filename"),
                file_size=data.get("file_size"),
                duration=data.get("duration"),
                width=data.get("width"),
                height=data.get("height"),
                order=data.get("order", idx),
            )
            media_list.append(media)

        created_list = await self.media_repo.create_many(media_list)
        await self.session.commit()
        logger.info(f"Added {len(created_list)} media items to post {post_id}")
        return created_list

    async def get_post_media(self, post_id: uuid.UUID) -> Sequence[PostMedia]:
        """
        게시글의 모든 미디어 조회.

        Args:
            post_id: 게시글 UUID

        Returns:
            미디어 목록 (order 순)
        """
        return await self.media_repo.get_by_post_id(post_id)

    async def get_media_by_id(self, media_id: uuid.UUID) -> PostMedia | None:
        """
        미디어 단건 조회.

        Args:
            media_id: 미디어 UUID

        Returns:
            PostMedia | None
        """
        return await self.media_repo.get_by_id(media_id)

    async def delete_media(self, media_id: uuid.UUID) -> bool:
        """
        미디어 삭제.

        Note: S3 파일 삭제는 별도로 처리해야 합니다.
        컨트롤러에서 S3 삭제 후 이 메서드를 호출하세요.

        Args:
            media_id: 미디어 UUID

        Returns:
            bool: 삭제 성공 여부
        """
        result = await self.media_repo.delete(media_id)
        if result:
            await self.session.commit()
            logger.info(f"Deleted media: {media_id}")
        return result

    async def delete_all_post_media(self, post_id: uuid.UUID) -> int:
        """
        게시글의 모든 미디어 삭제.

        Note: S3 파일 삭제는 별도로 처리해야 합니다.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 삭제된 미디어 수
        """
        count = await self.media_repo.delete_by_post_id(post_id)
        await self.session.commit()
        logger.info(f"Deleted {count} media items from post {post_id}")
        return count

    async def reorder_media(
        self,
        post_id: uuid.UUID,
        media_order: list[uuid.UUID],
    ) -> list[PostMedia]:
        """
        미디어 순서 재정렬.

        Args:
            post_id: 게시글 UUID
            media_order: 새 순서대로 정렬된 미디어 ID 목록

        Returns:
            재정렬된 PostMedia 목록
        """
        updated_media = []
        for idx, media_id in enumerate(media_order):
            media = await self.media_repo.update_order(media_id, idx)
            if media and media.post_id == post_id:
                updated_media.append(media)

        await self.session.commit()
        logger.info(f"Reordered {len(updated_media)} media items for post {post_id}")
        return updated_media

    async def get_media_count(self, post_id: uuid.UUID) -> int:
        """
        게시글의 미디어 개수.

        Args:
            post_id: 게시글 UUID

        Returns:
            int: 미디어 수
        """
        return await self.media_repo.count_by_post_id(post_id)
