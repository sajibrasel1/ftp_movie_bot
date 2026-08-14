#!/usr/bin/env python3
"""
Auto Category Detection System
Detects categories from movie title and metadata
"""

import re
import json
from typing import List, Dict, Set

class CategoryDetector:
    """Detects movie categories from title and metadata"""
    
    # Language detection patterns
    LANGUAGE_PATTERNS = {
        'Bengali': [
            r'\b(Bengali|Bangla|বাংলা)\b',
            r'\b(Hoichoi|Chorki|ZEE5)\b',  # Bengali streaming platforms
            r'\b(Kolkata|Dhaka)\b'
        ],
        'Hindi': [
            r'\b(Hindi|हिन्दी)\b',
            r'\b(Bollywood)\b',
            r'\b(Mumbai)\b'
        ],
        'Tamil': [
            r'\b(Tamil|தமிழ்)\b',
            r'\b(Kollywood|Chennai)\b'
        ],
        'Telugu': [
            r'\b(Telugu|తెలుగు)\b',
            r'\b(Tollywood|Hyderabad)\b'
        ],
        'English': [
            r'\b(English|Hollywood)\b',
            r'\b(ESub)\b',  # English subtitle indicator
        ],
        'Dual Audio': [
            r'\bDual\s+Audio\b',
            r'\b(Hindi[-\s]English|Hindi[-\s]Tamil|Hindi[-\s]Telugu)\b'
        ]
    }
    
    # Quality detection patterns
    QUALITY_PATTERNS = {
        '480p': [r'\b480p?\b', r'\bSD\b'],
        '720p HD': [r'\b720p?\b', r'\bHD\b'],
        '1080p Full HD': [r'\b1080p?\b', r'\bFull\s*HD\b', r'\bFHD\b'],
        '4K Ultra HD': [r'\b(4K|2160p)\b', r'\bUltra\s*HD\b', r'\bUHD\b']
    }
    
    # Content type patterns
    CONTENT_TYPE_PATTERNS = {
        'Web Series': [
            r'\bS\d{2}E\d{2}\b',  # S01E01 format
            r'\bSeason\s+\d+\b',
            r'\bWeb\s+Series\b',
            r'\b(Netflix|Amazon|Hoichoi|Chorki|ZEE5|Hotstar)\b'
        ],
        'Movie': [
            r'\bMovie\b',
            r'\bFilm\b',
            r'\b(WEB-DL|BluRay|DVDRip|HDRip)\b'
        ]
    }
    
    # Genre detection (basic - from common keywords)
    GENRE_PATTERNS = {
        'Action': [r'\b(Action|Fight|War|Battle)\b'],
        'Comedy': [r'\b(Comedy|Funny|Laugh)\b'],
        'Drama': [r'\b(Drama|Emotional)\b'],
        'Horror': [r'\b(Horror|Scary|Ghost|Zombie)\b'],
        'Romance': [r'\b(Romance|Love|Romantic)\b'],
        'Thriller': [r'\b(Thriller|Suspense|Mystery)\b'],
        'Sci-Fi': [r'\b(Sci-?Fi|Science Fiction|Space)\b'],
        'Fantasy': [r'\b(Fantasy|Magic|Wizard)\b']
    }
    
    def __init__(self):
        """Initialize detector"""
        self.detected = {
            'languages': set(),
            'qualities': set(),
            'content_types': set(),
            'genres': set()
        }
    
    def detect_from_title(self, title: str) -> Dict[str, List[str]]:
        """
        Detect all categories from movie title
        
        Args:
            title: Movie title string
            
        Returns:
            Dictionary with detected category types
        """
        self.detected = {
            'languages': set(),
            'qualities': set(),
            'content_types': set(),
            'genres': set()
        }
        
        # Detect language
        for lang, patterns in self.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    self.detected['languages'].add(lang)
                    break
        
        # Detect quality
        for quality, patterns in self.QUALITY_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    self.detected['qualities'].add(quality)
                    break
        
        # Detect content type
        for content_type, patterns in self.CONTENT_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    self.detected['content_types'].add(content_type)
                    break
        
        # Detect genre (basic)
        for genre, patterns in self.GENRE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, title, re.IGNORECASE):
                    self.detected['genres'].add(genre)
        
        # Convert sets to lists for JSON serialization
        return {
            'languages': list(self.detected['languages']),
            'qualities': list(self.detected['qualities']),
            'content_types': list(self.detected['content_types']),
            'genres': list(self.detected['genres'])
        }
    
    def get_category_slugs(self, title: str) -> List[str]:
        """
        Get category slugs that match this movie
        
        Args:
            title: Movie title
            
        Returns:
            List of category slugs to assign
        """
        detected = self.detect_from_title(title)
        slugs = []
        
        # Add language-based categories
        for lang in detected['languages']:
            if lang == 'Bengali':
                slugs.append('bengali-movies')
            elif lang == 'Hindi':
                slugs.append('hindi-movies')
            elif lang == 'Tamil':
                slugs.append('tamil-movies')
            elif lang == 'Telugu':
                slugs.append('telugu-movies')
            elif lang == 'English':
                slugs.append('english-movies')
            elif lang == 'Dual Audio':
                slugs.append('dual-audio')
        
        # Add quality-based categories
        for quality in detected['qualities']:
            if '480p' in quality or 'SD' in quality:
                slugs.append('480p')
            if '720p' in quality:
                slugs.append('720p-hd')
            elif '1080p' in quality:
                slugs.append('1080p-full-hd')
            elif '4K' in quality:
                slugs.append('4k-ultra-hd')
        
        # Add content type
        if 'Web Series' in detected['content_types']:
            slugs.append('web-series')
        
        # Add genre categories
        for genre in detected['genres']:
            slugs.append(genre.lower())
        
        return list(set(slugs))  # Remove duplicates
    
    def get_primary_language(self, title: str) -> str:
        """Get primary language for the movie"""
        detected = self.detect_from_title(title)
        
        # Priority order
        priority = ['Bengali', 'Hindi', 'Tamil', 'Telugu', 'English', 'Dual Audio']
        
        for lang in priority:
            if lang in detected['languages']:
                return lang
        
        return 'Unknown'
    
    def get_primary_genre(self, title: str) -> str:
        """Get primary genre for the movie"""
        detected = self.detect_from_title(title)
        
        if detected['genres']:
            return detected['genres'][0]
        
        return 'General'


def test_detector():
    """Test the category detector"""
    detector = CategoryDetector()
    
    test_titles = [
        "Malik (2026) Bengali WEB-DL - 720P | 1080P",
        "Heart Beat (2026) S03 Dual Audio [Hindi-Tamil]",
        "The Odyssey (2026) Hollywood Action Movie 4K",
        "Atonko Season 1 Part 2 (2026) | Bangla Web Series",
        "Johnny Jumper JHS ESub (2026) [720p HD]"
    ]
    
    print("🎬 Category Detection Test\n" + "="*50)
    
    for title in test_titles:
        print(f"\n📽️  {title}")
        categories = detector.get_category_slugs(title)
        detected = detector.detect_from_title(title)
        primary_lang = detector.get_primary_language(title)
        primary_genre = detector.get_primary_genre(title)
        
        print(f"   Language: {primary_lang}")
        print(f"   Genre: {primary_genre}")
        print(f"   Categories: {', '.join(categories)}")
        print(f"   Detected: {json.dumps(detected, indent=6)}")


if __name__ == '__main__':
    test_detector()
