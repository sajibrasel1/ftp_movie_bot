# 🔄 MLSBD Domain Change Guide

MLSBD সাইট frequently domain change করে (যেমন `.co` → `.biz` → `.net` ইত্যাদি)।

এই bot **automatic domain detection** করে - আপনাকে কিছু করতে হবে না!

---

## 🤖 **Auto-Detection System**

Bot automatically handle করে domain changes:

### ✅ **যখন domain change হয়:**

1. Bot current domain-এ access করার চেষ্টা করবে
2. যদি fail হয় (timeout/404/503 etc), bot automatically:
   - 🔍 Google search করবে "mlsbd movies"
   - 📋 নতুন working domains খুঁজে বের করবে
   - ✅ প্রতিটা domain test করবে
   - 💾 Working domain database-এ save করবে
   - 🔄 নতুন domain দিয়ে scraping continue করবে

### **আপনাকে কিছু করতে হবে না!** 🎉

---

## 🔍 **How Auto-Detection Works**

```
┌─────────────────────────────────────┐
│  Bot tries current domain           │
│  (e.g. https://mlsbd.co)           │
└─────────────┬───────────────────────┘
              │
              ├─ Success? ✅ Continue scraping
              │
              └─ Failed? ❌
                  │
                  ├─ Test common domains:
                  │   mlsbd.biz, mlsbd.net, etc.
                  │
                  ├─ If none work, Google search:
                  │   "mlsbd movies download"
                  │
                  ├─ Extract domains from results
                  │
                  ├─ Test each domain
                  │
                  └─ Update database ✅
                      │
                      └─ Continue scraping with new domain
```

---

## 📋 **Tested Domain Priority**

Bot tests domains in this order:

1. **Common known domains** (fast):
   - mlsbd.co
   - mlsbd.biz
   - mlsbd.net
   - mlsbd.shop
   - mlsbd.site
   - mlsbd.xyz
   - mlsbd.info
   - mlsbd.me

2. **Google search results** (if above fail):
   - Searches: "mlsbd movies download site"
   - Extracts all MLSBD-related domains
   - Tests each one

3. **Domain validation**:
   - Must be accessible (HTTP 200)
   - Must contain MLSBD-specific content
   - Must have movie-related keywords

---

## ✅ **Manual Override (Optional)**

যদি auto-detection কোন কারণে fail করে, তাহলে manually update করতে পারবেন:

### Method 1: Python Script
```bash
python update_mlsbd_domain.py https://mlsbd.biz
```

### Method 2: Direct SQL
```sql
UPDATE mlsbd_config 
SET config_value = 'https://mlsbd.biz' 
WHERE config_key = 'base_url';
```

---

## 🔧 **Manual Testing**

Auto-detection test করতে:

```bash
cd ~/movie_bot_new/ftp_movie_bot
python3 auto_detect_mlsbd_domain.py
```

Output দেখবেন:
```
🔍 MLSBD Auto Domain Detection Starting...
📋 Testing common MLSBD domains...
   Testing: https://mlsbd.co
❌ Domain https://mlsbd.co test failed
   Testing: https://mlsbd.biz
✅ Domain https://mlsbd.biz appears to be valid
✅ Found working domain: https://mlsbd.biz
✅ Database updated with new domain
✅ Success! New domain: https://mlsbd.biz
```

---

## 📊 **Monitoring**

Cron log দেখুন auto-detection কাজ করছে কিনা:

```bash
tail -f ~/movie_bot_new/ftp_movie_bot/logs/mlsbd_trigger.log
```

Log-এ দেখবেন:
```
⚠️ Current domain https://mlsbd.co returned status 503
🔍 Attempting auto-detection of new MLSBD domain...
📋 Testing common MLSBD domains...
✅ Found working domain: https://mlsbd.biz
✅ Database updated with new domain
🔄 Retrying crawl with new domain...
✅ Crawl completed successfully
```

---

## 🎯 **Benefits**

✅ **Zero manual intervention** - bot নিজে handle করবে  
✅ **Instant recovery** - domain fail হলে automatic switch  
✅ **Google-powered** - latest domain খুঁজে বের করবে  
✅ **Validation** - working domain নিশ্চিত করে  
✅ **Persistent** - database-এ save করে future use এর জন্য  

---

## 🚨 **Important Notes**

1. **Auto-detection চালু আছে** - কোন configuration লাগবে না
2. **Google dependency** - internet connection লাগবে (cPanel server-এ আছে)
3. **Fallback আছে** - common domains আগে try করবে, then Google
4. **One-time per failure** - একবার detect করলে পরের run গুলিতে নতুন domain use হবে

---

## 🎬 **Example Scenario**

```
Day 1: Bot running with mlsbd.co ✅
Day 2: MLSBD changes to mlsbd.biz
       → Bot detects failure
       → Auto-searches Google
       → Finds mlsbd.biz
       → Updates database
       → Continues scraping ✅
Day 3+: Bot uses mlsbd.biz automatically ✅
```

**আপনার কোন কাজ নেই!** 🎉

---

**তৈরি করেছেন:** AI Assistant  
**Version:** 1.0  
**Last Updated:** 2026-08-12
