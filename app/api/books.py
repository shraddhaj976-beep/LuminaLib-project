from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.base import get_db
from app.db.models import Book, Borrow, User, UserInteraction, UserPreference
from app.services.storage import get_storage
from app.tasks.tasks import generate_summary_task

router = APIRouter(prefix="/books", tags=["Books"])
ROOT_USERNAME = "rootuser"


def ensure_root_user(user: User) -> None:
    username = user.email.split("@", 1)[0].lower() if user.email else ""
    if username != ROOT_USERNAME:
        raise HTTPException(
            status_code=403,
            detail="User does not have access for this action",
        )


@router.post("/")
async def upload_book(
    title: str = Form(...),
    author: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_root_user(current_user)
    file.file.seek(0)
    storage = get_storage()
    key = f"books/{uuid4()}_{file.filename}"
    content_path = await storage.upload(key, file.file)

    book = Book(
        title=title,
        author=author,
        content_path=content_path,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    generate_summary_task.delay(book.id)
    return {"msg": "Book uploaded", "title": title, "author": author, "id": book.id}


@router.get("/")
async def list_books(
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if page < 1 or page_size < 1 or page_size > 100:
        raise HTTPException(status_code=400, detail="Invalid pagination params")
    offset = (page - 1) * page_size
    result = await db.execute(select(Book).order_by(Book.id).offset(offset).limit(page_size))
    books = result.scalars().all()
    borrower_counts_result = await db.execute(
        select(
            Borrow.book_id,
            func.count(func.distinct(Borrow.user_id)).label("borrower_count"),
        ).group_by(Borrow.book_id)
    )
    borrower_counts = {row.book_id: row.borrower_count for row in borrower_counts_result}
    return [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "content_path": b.content_path,
            "summary": b.summary,
            "tags": b.tags,
            "created_at": b.created_at,
            "borrower_count": borrower_counts.get(b.id, 0),
        }
        for b in books
    ]


@router.put("/{book_id}")
async def update_book(
    book_id: int,
    title: str | None = Form(None),
    author: str | None = Form(None),
    file: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_root_user(current_user)
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    if title:
        book.title = title
    if author:
        book.author = author
    if file:
        file.file.seek(0)
        storage = get_storage()
        key = f"books/{uuid4()}_{file.filename}"
        content_path = await storage.upload(key, file.file)
        if book.content_path:
            await storage.delete(book.content_path)
        book.content_path = content_path
    await db.commit()
    return {"msg": "Book updated"}


@router.delete("/{book_id}")
async def delete_book(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ensure_root_user(current_user)
    result = await db.execute(select(Book).where(Book.id == book_id))
    book = result.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    has_active_borrow = (
        await db.execute(
            select(Borrow.id)
            .where(
                Borrow.book_id == book_id,
                Borrow.status == "borrowed",
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if has_active_borrow:
        raise HTTPException(
            status_code=409,
            detail="Book is currently borrowed and cannot be deleted",
        )
    storage = get_storage()
    if book.content_path:
        await storage.delete(book.content_path)
    await db.execute(delete(Borrow).where(Borrow.book_id == book_id))
    await db.delete(book)
    await db.commit()
    return {"msg": "Book deleted"}


@router.post("/{book_id}/borrow")
async def borrow_book(
    book_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="User mismatch for borrow action")
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = (
        await db.execute(
            select(Borrow).where(
                Borrow.book_id == book_id,
                Borrow.user_id == user_id,
                Borrow.status == "borrowed",
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="You already borrowed this book")

    print(f"User {user_id} is borrowing book {book_id}")
    borrow = Borrow(book_id=book_id, user_id=user_id, status="borrowed")
    db.add(borrow)
    db.add(UserInteraction(user_id=user_id, book_id=book_id, event_type="borrow"))
    if book.tags:
        for tag in book.tags:
            pref = (
                await db.execute(
                    select(UserPreference).where(
                        UserPreference.user_id == user_id,
                        UserPreference.tag == tag,
                    )
                )
            ).scalar_one_or_none()
            if pref:
                pref.weight = float(pref.weight) + 1.0
            else:
                db.add(UserPreference(user_id=user_id, tag=tag, weight=1.0))
    await db.commit()
    await db.refresh(borrow)
    return {"msg": f"Book {book_id} borrowed", "borrow_id": borrow.id}


@router.post("/{book_id}/return")
async def return_book(
    book_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if user_id != current_user.id:
        raise HTTPException(status_code=403, detail="User mismatch for return action")
    borrow = (
        await db.execute(
            select(Borrow).where(
                Borrow.book_id == book_id,
                Borrow.user_id == user_id,
                Borrow.status == "borrowed",
            )
        )
    ).scalar_one_or_none()
    if not borrow:
        raise HTTPException(status_code=404, detail="Active borrow not found")

    borrow_id = borrow.id
    borrow.status = "returned"
    await db.commit()
    return {"msg": f"Book {book_id} returned", "borrow_id": borrow_id}


@router.get("/borrow")
async def list_borrowed_books(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Borrow)
        .where(
            Borrow.user_id == current_user.id,
        )
        .order_by(Borrow.id.desc())
    )
    borrows = result.scalars().all()
    if not borrows:
        return []

    book_ids = [b.book_id for b in borrows]
    books_result = await db.execute(select(Book).where(Book.id.in_(book_ids)))
    books = {b.id: b for b in books_result.scalars().all()}

    return [
        {
            "User_id": current_user.id,
            "borrow_id": b.id,
            "book_id": b.book_id,
            "title": books.get(b.book_id).title if books.get(b.book_id) else None,
            "author": books.get(b.book_id).author if books.get(b.book_id) else None,
            "status": b.status,
        }
        for b in borrows
    ]
