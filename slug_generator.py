#!/usr/bin/env python3
"""
Slug Generator Helper
=====================
Generates SEO-friendly URL slugs from movie titles
"""

import re
import unicodedata


def generate_slug(title):
    """
    Generate a SEO-friendly slug from movie title
    
    Args:
        title (str): Movie title
        
    Returns:
        str: URL-safe slug
        
    Examples:
        >>> generate_slug("Malik (2026) Bengali")
        'malik-2026-bengali'
        
        >>> generate_slug("Heart Beat S03E01-12 [Hindi-Tamil]")
        'heart-beat-s03e01-12-hindi-tamil'
    """
    if not title:
        return ""
    
    # Convert to lowercase
    slug = title.lower()
    
    # Normalize unicode characters (handles accents, etc.)
    slug = unicodedata.normalize('NFKD', slug)
    slug = slug.encode('ascii', 'ignore').decode('ascii')
    
    # Remove special characters, keep alphanumeric and spaces
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    
    # Replace multiple spaces/hyphens with single hyphen
    slug = re.sub(r'[\s-]+', '-', slug)
    
    # Remove leading/trailing hyphens
    slug = slug.strip('-')
    
    # Limit length to 200 characters
    if len(slug) > 200:
        slug = slug[:200].rsplit('-', 1)[0]
    
    return slug


def ensure_unique_slug(cursor, slug, movie_id=None):
    """
    Ensure slug is unique in database, append number if needed
    
    Args:
        cursor: Database cursor
        slug (str): Proposed slug
        movie_id (int, optional): Movie ID to exclude from uniqueness check
        
    Returns:
        str: Unique slug
    """
    original_slug = slug
    counter = 1
    
    while True:
        # Check if slug exists
        if movie_id:
            cursor.execute(
                "SELECT id FROM mlsbd_movies WHERE slug = %s AND id != %s",
                (slug, movie_id)
            )
        else:
            cursor.execute(
                "SELECT id FROM mlsbd_movies WHERE slug = %s",
                (slug,)
            )
        
        if cursor.fetchone() is None:
            # Slug is unique
            return slug
        
        # Slug exists, try with counter
        counter += 1
        slug = f"{original_slug}-{counter}"


if __name__ == "__main__":
    # Test cases
    test_titles = [
        "Malik (2026) Bengali WEB-DL – 720P | 1080P",
        "Heart Beat (2026) S03E01-12 Dual Audio [Hindi ORG-Tamil]",
        "Johnny Jumper JHS ESub (2026) [720p HD]",
        "In the Grey Blu Ray ESub (2026) [720p HD]",
        "Atonko Season 1 Part 2 (2026) | Bangla Web Series",
        "Test Movie!!! With @Special #Characters & Symbols",
    ]
    
    print("Slug Generator Test Cases:")
    print("=" * 80)
    
    for title in test_titles:
        slug = generate_slug(title)
        print(f"Title: {title}")
        print(f"Slug:  {slug}")
        print("-" * 80)
