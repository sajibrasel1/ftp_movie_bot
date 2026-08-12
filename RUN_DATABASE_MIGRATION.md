# Database Migration - Add download_links Column

## Purpose
Add `download_links` JSON column to store multiple download sources (GDFlix, MultiCloud, FilePress) for fallback support.

## Steps to Run on Server

### Method 1: Direct SSH Command
```bash
ssh techandc@grreseller1.hosttoweb.net

cd ~/movie_bot_new/ftp_movie_bot

mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts < add_download_links_column.sql
```

### Method 2: MySQL Command Line
```bash
ssh techandc@grreseller1.hosttoweb.net

mysql -h localhost -u techandc_bot -p'12345Sajibs6@' techandc_prompts

# Then run:
ALTER TABLE mlsbd_movies 
ADD COLUMN download_links JSON DEFAULT NULL COMMENT 'All available download links' 
AFTER gdflix_url;

# Verify:
DESCRIBE mlsbd_movies;
```

## Expected Result
```
+------------------+--------------+------+-----+---------+-------+
| Field            | Type         | Null | Key | Default | Extra |
+------------------+--------------+------+-----+---------+-------+
| gdflix_url       | varchar(500) | YES  | UNI | NULL    |       |
| download_links   | json         | YES  |     | NULL    |       |
| direct_download_ | text         | YES  |     | NULL    |       |
+------------------+--------------+------+-----+---------+-------+
```

## JSON Structure
```json
{
  "gdflix": "https://gdflix.dev/file/NlfPCAUax8tAokO",
  "multicloud": "https://new.multicloudlinks.com/view/k9lng8",
  "filepress": "https://new2.filepress.baby/file/6a7389aeecbe9f1114296613",
  "hubcloud": "https://hubcloud.link/file/xyz123"
}
```

## Verification Query
```sql
SELECT id, movie_title, 
       JSON_EXTRACT(download_links, '$.gdflix') as gdflix,
       JSON_EXTRACT(download_links, '$.multicloud') as multicloud
FROM mlsbd_movies 
WHERE download_links IS NOT NULL 
LIMIT 5;
```

## Rollback (if needed)
```sql
ALTER TABLE mlsbd_movies DROP COLUMN download_links;
```
