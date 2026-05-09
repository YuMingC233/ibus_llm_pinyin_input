COMMON_CANDIDATES = {
    "nihao": ["你好", "你号"],
    "ninhao": ["您好"],
    "zaijian": ["再见"],
    "xiexie": ["谢谢"],
    "buhaoyisi": ["不好意思"],
    "meiguanxi": ["没关系"],
    "meiyou": ["没有"],
    "keyi": ["可以"],
    "bukeyi": ["不可以"],
    "wo": ["我"],
    "ni": ["你"],
    "ta": ["他", "她", "它"],
    "women": ["我们"],
    "nimen": ["你们"],
    "tamen": ["他们", "她们"],
    "de": ["的", "得", "地"],
    "shi": ["是", "时", "事"],
    "you": ["有", "又", "由"],
    "zai": ["在", "再"],
    "he": ["和", "很"],
    "le": ["了"],
    "ma": ["吗"],
    "ba": ["吧"],
    "yao": ["要"],
    "xiang": ["想", "像", "向"],
    "kan": ["看"],
    "shuo": ["说"],
    "xie": ["写", "谢"],
    "zuo": ["做", "作", "坐"],
    "qu": ["去"],
    "lai": ["来"],
    "hao": ["好", "号"],
    "haishi": ["还是"],
    "haishimeiyou": ["还是没有"],
    "zhongwen": ["中文"],
    "shurufa": ["输入法"],
    "pinyin": ["拼音"],
    "houxuan": ["候选"],
    "houxuanci": ["候选词"],
    "baocuo": ["报错"],
    "bug": ["bug"],
    "xiufu": ["修复"],
    "jintian": ["今天"],
    "mingtian": ["明天"],
    "zuotian": ["昨天"],
}


def normalize_pinyin(pinyin):
    return "".join(ch for ch in pinyin.lower() if ch.isalpha())


def get_local_candidates(pinyin, limit=5):
    key = normalize_pinyin(pinyin)
    if not key:
        return []

    candidates = COMMON_CANDIDATES.get(key, [])
    return candidates[:limit]
