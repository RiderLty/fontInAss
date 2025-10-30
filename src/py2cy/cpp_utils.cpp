#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ctype.h>
#include <stdbool.h>
#include <iostream>
#include <set>
#include <unordered_map>
#include <string_view>
#include <algorithm>


using namespace std;

#define startsWith(str, prefix) (strncmp((str), (prefix), strlen(prefix)) == 0)
#ifdef _WIN32
    #define startsWithIgnoreCase(str, prefix) (_strnicmp((str), (prefix), strlen(prefix)) == 0)
#elif __linux__
    #define startsWithIgnoreCase(str, prefix) (strncasecmp((str), (prefix), strlen(prefix)) == 0)
#endif
#define startsWith_SV(str, prefix) ((str).compare(0, strlen(prefix), prefix) == 0)

#ifdef _WIN32
#define strtok_rs strtok_s
#elif __linux__
#define strtok_rs strtok_r
#endif

#define DEBUG_ON false
#if DEBUG_ON
#define DEBUG(fmt, args...) printf(fmt, ##args);
#define DEBUG_SV(args...) \
    do                    \
    {                     \
        cout << args;     \
    } while (0)
#else
#define DEBUG(...)    // 不输出任何信息
#define DEBUG_SV(...) // 不输出任何信息
#endif

void strip(string_view &str)
{
    // 去除开头的空白字符
    while (isspace((unsigned char)str.front()))
    {
        str.remove_prefix(1);
    }

    // 去除结尾的空白字符
    while (!str.empty() && isspace((unsigned char)str.back()))
    {
        str.remove_suffix(1);
    }
}

void trimLeadingChars(string_view &str, char ch)
{
    // 去除开头的空白字符
    while ((unsigned char)str.front() == ch)
    {
        str.remove_prefix(1);
    }
}

char *trimLeadingChars(char *str, char ch)
{
    if (str == NULL)
    {
        return NULL;
    }
    // 去除开头的空白字符
    char *start = str;
    while ((unsigned char)*start == ch)
    {
        start++;
    }
    return start;
}

void trimLC_strip(string_view &str, char ch)
{
    while ((unsigned char)str.front() == ch || isspace((unsigned char)str.front()))
    {
        str.remove_prefix(1);
    }
    while (!str.empty() && isspace((unsigned char)str.back()))
    {
        str.remove_suffix(1);
    }
}

struct fontKey
{
    int32_t italic;
    int32_t weight;
    string_view fontName;
    bool operator==(const fontKey &other) const
    {
        return fontName.compare(other.fontName) == 0 && weight == other.weight && italic == other.italic;
    }
};

struct fontKeyHash
{
    size_t operator()(const fontKey &fontKey) const
    {
        size_t h1 = hash<string_view>()(fontKey.fontName);
        size_t h2 = hash<int32_t>()(fontKey.weight);
        size_t h3 = hash<int32_t>()(fontKey.italic);
        return h1 ^ (h2 << 1) ^ (h3 << 2); // 混合哈希值
    }
};

struct CharPtrHash
{
    size_t operator()(const char *str) const
    {
        size_t hash = 0;
        while (*str)
        {
            hash = hash * 131 + *str++; // 简单的哈希算法
        }
        return hash;
    }
};

// 自定义键比较函数
struct CharPtrEqual
{
    bool operator()(const char *str1, const char *str2) const
    {
        return strcmp(str1, str2) == 0;
    }
};

uint32_t nextCode(const char *str, int *index)
// 获取当前code的unicode值，并移动index到下一个开始，返回-1表示结束
{
    unsigned char *s = (unsigned char *)str + *index;
    uint32_t unicode = 0;
    if (*s == '\0')
    {
        return -1; // 结束，表示没有更多字符
    }
    if (*s < 0x80)
    {
        unicode = *s;
        (*index)++;
        return unicode;
    }

    // 解析双字节字符 (110xxxxx 10xxxxxx)
    if ((*s & 0xE0) == 0xC0)
    {
        unicode = (*s & 0x1F) << 6;
        s++;
        unicode |= (*s & 0x3F);
        (*index) += 2;
        return unicode;
    }

    // 解析三字节字符 (1110xxxx 10xxxxxx 10xxxxxx)
    if ((*s & 0xF0) == 0xE0)
    {
        unicode = (*s & 0x0F) << 12;
        s++;
        unicode |= (*s & 0x3F) << 6;
        s++;
        unicode |= (*s & 0x3F);
        (*index) += 3;
        return unicode;
    }

    // 解析四字节字符 (11110xxx 10xxxxxx 10xxxxxx 10xxxxxx)
    if ((*s & 0xF8) == 0xF0)
    {
        unicode = (*s & 0x07) << 18;
        s++;
        unicode |= (*s & 0x3F) << 12;
        s++;
        unicode |= (*s & 0x3F) << 6;
        s++;
        unicode |= (*s & 0x3F);
        (*index) += 4;
        return unicode;
    }

    // 如果不是有效的UTF-8字符，返回-1
    return -1;
}

char *uint32ToUnicodeChar(uint32_t unicode)
{
    // 分配足够的内存以存储一个字符和终止符
    char *result = (char *)malloc(sizeof(char) * 5); // 4个十六进制字符 + 1个终止符
    if (result == NULL)
    {
        return NULL; // 内存分配失败
    }

    // 将整数转换为 UTF-8 字符串
    if (unicode < 0x80)
    {
        // 1字节字符
        result[0] = (char)unicode;
        result[1] = '\0';
    }
    else if (unicode < 0x800)
    {
        // 2字节字符
        result[0] = (char)((unicode >> 6) | 0xC0);
        result[1] = (char)((unicode & 0x3F) | 0x80);
        result[2] = '\0';
    }
    else if (unicode < 0x10000)
    {
        // 3字节字符
        result[0] = (char)((unicode >> 12) | 0xE0);
        result[1] = (char)(((unicode >> 6) & 0x3F) | 0x80);
        result[2] = (char)((unicode & 0x3F) | 0x80);
        result[3] = '\0';
    }
    else
    {
        // 4字节字符（Unicode范围在 0x10000 到 0x10FFFF 之间）
        result[0] = (char)((unicode >> 18) | 0xF0);
        result[1] = (char)(((unicode >> 12) & 0x3F) | 0x80);
        result[2] = (char)(((unicode >> 6) & 0x3F) | 0x80);
        result[3] = (char)((unicode & 0x3F) | 0x80);
        result[4] = '\0';
    }

    return result; // 返回转换后的字符串
}

bool isDigitStr(char *str)
{
    char *ptr = str;
    if (*ptr == '-')
    {
        ptr++;
    }
    if (*ptr == '\0')
    {
        return false;
    }
    while (*ptr)
    {
        if (!isdigit((unsigned char)*ptr))
        {
            return false;
        }
        ptr++;
    }
    return true;
}

bool isDigitStr_SV(std::string_view sv) {
    if (sv.empty()) return false;  // 空字符串直接返回false

    // 处理负数情况
    if (sv.front() == '-') {
        // 负号后至少需要1个数字字符
        return sv.size() > 1 && all_of(sv.begin() + 1, sv.end(), 
            [](char c) { return c >= '0' && c <= '9'; });
    }
    // 非负数情况：所有字符均为数字
    return all_of(sv.begin(), sv.end(), 
        [](char c) { return c >= '0' && c <= '9'; });
}

bool is_zero_and_space(char *str)
{
    // 是否由仅由0与空格构成
    // 用于Format内，仅区分是否为0
    size_t len = strlen(str);
    for (size_t i = 0; i < len; i++)
    {
        if ((!isspace(str[i])) && (str[i] != '0'))
            return false;
    }
    return true;
}

// if (startsWith(code, "rnd") && (((strcmp(code + 3, "x") || strcmp(code + 3, "y") || strcmp(code + 3, "z")) && isDigitStr(code + 4)) || (isDigitStr(code + 3))))
bool is_rnd_code(string_view &code)
{
    if (code.size() < 3)
        return false;
    if (code.substr(0, 3) == "rnd")
    {
        if (code.size() == 3)
            return true;
        if (code[3] == 'x' || code[3] == 'y' || code[3] == 'z')
        {
            if (code.size() > 4 && isDigitStr_SV(code.substr(4)))
                return true;
        }
        else if (isDigitStr_SV(code.substr(3)))
            return true;
    }
    // 其他情况
    return false;
}

extern "C"
{
    unsigned char *analyseAss_CPP(const char *__assStr)
    {
        size_t assStrLen = strlen(__assStr);
        char *assStr = (char *)malloc(assStrLen + 1);
        memcpy(assStr, __assStr, assStrLen + 1);

        unordered_map<fontKey, set<uint32_t>, fontKeyHash> fontCharList;
        unordered_map<string_view, fontKey> styleFont;
        unordered_map<string_view, string_view> fontSubsetRename;

        int state = 0;
        int styleNameIndex = -1;
        int fontNameIndex = -1;
        int boldIndex = -1;
        int italicIndex = -1;
        int eventStyleIndex = -1;
        int eventTextIndex = -1;
        char *lineSplitPtr = NULL;
        string_view defaultStyleName;
        
        auto analyssLine = [&](char *line)
        {
            char *dialogue = line + strlen("Dialogue:");
            int commaCount = 0;
            int styleStart = 0;
            int styleEnd = 0;
            int textStart = 0;
            int dialogueLen = strlen(dialogue);
            // DEBUG("\n%s\n", dialogue);
            for (int index = 0; index < dialogueLen; index++)
            {
                // DEBUG("%s\n", dialogue + index);
                if ((char)dialogue[index] == ',' || index == 0)
                {
                    commaCount += 1;
                    if (commaCount == eventStyleIndex + 1)
                    {
                        styleStart = index + 1;
                    }
                    if (commaCount == eventStyleIndex + 2)
                    {
                        styleEnd = index;
                    }
                    if (commaCount == eventTextIndex + 1)
                    {
                        textStart = index + 1;
                        break;
                    }
                }
            }
            int styleLen = styleEnd - styleStart;
            string_view styleName(dialogue + styleStart, styleLen);
            trimLC_strip(styleName, '*');
            char *text = dialogue + textStart;
            struct fontKey lineDefaultFontInfo;
            if (styleFont.find(styleName) == styleFont.end())
            {
                DEBUG_SV("未知style 使用默认 " << defaultStyleName << endl);
                lineDefaultFontInfo = styleFont[defaultStyleName];
            }
            else
            {
                lineDefaultFontInfo = styleFont[styleName];
            }
            struct fontKey currentFontInfo = lineDefaultFontInfo;

            if (fontCharList.find(currentFontInfo) == fontCharList.end())
            {
                if (fontCharList.find(currentFontInfo) == fontCharList.end())
                {
                    DEBUG_SV(currentFontInfo.italic << " " << currentFontInfo.weight << " " << currentFontInfo.fontName << "未找到，创建新的" << endl);
                    fontCharList[currentFontInfo] = set<uint32_t>();
                }
            }

            set<uint32_t> *currentCharSet = &fontCharList[currentFontInfo];
            int textState = 0;
            int codeStart = -1;
            bool drawMod = false;
            int index = 0;
            int textLen = strlen(text);
            DEBUG("=======================================================\ntext:%s\n", text);
            while (index < textLen)
            {
                bool addChar = false;
                char ch = text[index];
                bool fontKeyChanged = false;
                if (textState == 0)
                {
                    fontKeyChanged = false;
                    if (ch == '{')
                    // 这里仅依照MPV的测试结果解析
                    {
                        while (text[index] != '}' && text[index] != '\0' && text[index] != '\\' && index < textLen)
                        {
                            index++;
                        }
                        if (text[index] == '\\')
                        {
                            textState = 1;
                        }
                    }
                    else if (drawMod)
                    {
                    }
                    else if (ch == '\\') // 转义字符
                    {
                        // index++;
                        char ch_next = text[index + 1]; // 检查下一个字符
                        if (ch_next == '\0')
                        {
                            break;
                        }
                        else
                        {
                            index++; // 不为结束则跳转下一字符
                            if (!(ch_next == '{' || ch_next == '}' || ch_next == 'n' || ch_next == 'N' || ch_next == 'h'))
                            {
                                addChar = true; // 不为特殊字符则添加
                            }
                        }
                    }
                    else
                    {
                        addChar = true;
                    }
                }
                else if (textState == 1)
                {
                    codeStart = index;
                    while (true)
                    {
                        if (text[index] == '}')
                        {
                            textState = 0;
                            break;
                        }
                        if (text[index] == '\\')
                        {
                            textState = 1;
                            break;
                        }
                        index++;
                    }
                    char *codeStartPtr = text + codeStart;
                    int codeLen = index - codeStart;
                    string_view code(codeStartPtr, codeLen);
                    // 去除code尾部的空格
                    while (code.size() > 1 && isspace((unsigned char)code.back()))
                    {
                        code.remove_suffix(1);
                    }
                    if (is_rnd_code(code))
                    {
                    }
                    else if (startsWith_SV(code, "p"))
                    {
                        if (codeLen > 1 && isDigitStr_SV(code.substr(1)))
                            drawMod = code[1] != '0';
                    }
                    else if (startsWith_SV(code, "fn"))
                    {
                        fontKeyChanged = true;
                        if (codeLen == 2)
                            currentFontInfo.fontName = lineDefaultFontInfo.fontName;
                        else
                        {
                            currentFontInfo.fontName = string_view(codeStartPtr + 2, codeLen - 2); // 不能指向code，code会变，要指向原始
                            trimLC_strip(currentFontInfo.fontName, '@');
                            DEBUG_SV("fontName切换" << currentFontInfo.fontName << endl);
                        }
                    }
                    else if (startsWith_SV(code, "r"))
                    {
                        fontKeyChanged = true;
                        string_view rStyleName(codeStartPtr + 1, codeLen - 1);
                        trimLC_strip(rStyleName, '*');
                        if (rStyleName.empty()) // 空的
                            currentFontInfo = lineDefaultFontInfo;
                        else
                        {
                            if (styleFont.find(rStyleName) == styleFont.end())
                                currentFontInfo = lineDefaultFontInfo;
                            else
                                currentFontInfo = styleFont[rStyleName];
                        }
                        DEBUG_SV("style切换" << rStyleName << endl);
                    }
                    else if (startsWith_SV(code, "b"))
                    {
                        if (codeLen == 1)
                        {
                            currentFontInfo.weight = lineDefaultFontInfo.weight;
                            fontKeyChanged = true;
                        }
                        else if (isDigitStr_SV(code.substr(1)))
                        {
                            fontKeyChanged = true;
                            int32_t bold = static_cast<int32_t>(atoi(code.data() + 1));
                            if (bold == 0)
                                currentFontInfo.weight = 400;
                            else if (bold == 1)
                                currentFontInfo.weight = 700;
                            else
                                currentFontInfo.weight = bold;
                        }
                    }
                    else if (startsWith_SV(code, "i"))
                    {
                        if (codeLen == 1)
                        {
                            currentFontInfo.italic = lineDefaultFontInfo.italic;
                            fontKeyChanged = true;
                        }
                        else if (isDigitStr_SV(code.substr(1)))
                        {
                            currentFontInfo.italic = code[1] == '0' ? 0 : 1;
                            fontKeyChanged = true;
                        }
                    }
                }
                if (fontKeyChanged)
                {
                    if (fontCharList.find(currentFontInfo) == fontCharList.end())
                    {
                        if (fontCharList.find(currentFontInfo) == fontCharList.end())
                        {
                            DEBUG_SV(currentFontInfo.italic << " " << currentFontInfo.weight << " " << currentFontInfo.fontName << "未找到，创建新的" << endl);
                            fontCharList[currentFontInfo] = set<uint32_t>();
                        }
                    }
                    currentCharSet = &fontCharList[currentFontInfo];
                }
                if (addChar)
                {
                    uint32_t unicode = nextCode(text, &index);
                    if (unicode != '\r')
                    {
                        DEBUG_SV(currentFontInfo.fontName << "\t" << currentFontInfo.weight << "\t" << currentFontInfo.italic << ":" << uint32ToUnicodeChar(unicode) << "(" << unicode << ")" << endl);
                        currentCharSet->insert(unicode);
                    }
                }
                else
                {
                    index++;
                }
            }
            DEBUG("\n\n");
        };

        for (char *line = strtok_rs((char *)assStr, "\n", &lineSplitPtr); line != NULL; line = strtok_rs(NULL, "\n", &lineSplitPtr))
        {
            DEBUG("line:%s\n", line);
            if (strlen(line) < 1) // 小于最小长度，不用处理
                continue;

            if (state == 0)
            {
                if (startsWith(line, "[V4+ Styles]") || startsWith(line, "[V4 Styles]"))
                {
                    state = 1;
                }
                else if (startsWithIgnoreCase(line, "; Font Subset:"))
                {
                    string_view replacedName(line + strlen("; Font Subset: "), 8);
                    string_view originName(line + strlen("; Font Subset: 59W6OVGX - "), strlen(line) - strlen("; Font Subset: 59W6OVGX - "));
                    while (!originName.empty() && isspace(originName.back()))
                    {
                        originName.remove_suffix(1);
                    }
                    fontSubsetRename[replacedName] = originName;
                }
            }
            else if (state == 1)
            {
                state = 2;
                if (startsWith(line, "Format:"))
                {
                    char *format = line + strlen("Format:");
                    int index = 0;
                    char *tokenSplitPtr = NULL;
                    char *token = strtok_rs(format, ",", &tokenSplitPtr);
                    while (token != NULL)
                    {
                        if (strstr(token, "Name"))
                            styleNameIndex = index;
                        else if (strstr(token, "Fontname"))
                            fontNameIndex = index;
                        else if (strstr(token, "Bold"))
                            boldIndex = index;
                        else if (strstr(token, "Italic"))
                            italicIndex = index;
                        token = strtok_rs(NULL, ",", &tokenSplitPtr);
                        index++;
                    }
                    DEBUG(" styleNameIndex, fontNameIndex, boldIndex, italicIndex [%d,%d,%d,%d]\n", styleNameIndex, fontNameIndex, boldIndex, italicIndex);
                }
                else
                {
                    DEBUG("解析Style格式失败: %s\n", line);
                    return NULL;
                }
            }
            else if (state == 2)
            {
                if (startsWith(line, "[Events]"))
                {
                    state = 3;
                }
                else if (startsWith(line, "Style:"))
                {
                    char *style = line + strlen("Style:");
                    int index = 0;
                    char *tokenSplitPtr = NULL;
                    char *token = strtok_rs(style, ",", &tokenSplitPtr);
                    string_view styleName;
                    string_view fontName;
                    int32_t weight = 400;
                    int32_t italic = 0;
                    while (token != NULL)
                    {
                        if (index == styleNameIndex)
                        {
                            styleName = string_view(token);
                            trimLC_strip(styleName, '*');
                        }
                        else if (index == fontNameIndex)
                        {
                            fontName = string_view(token);
                            trimLC_strip(fontName, '@');
                        }
                        else if (index == boldIndex)
                        {
                            if (!is_zero_and_space(token))
                                weight = 700;
                        }
                        else if (index == italicIndex)
                        {
                            if (!is_zero_and_space(token))
                                italic = 1; // 0 则false 其他都为true
                        }
                        token = strtok_rs(NULL, ",", &tokenSplitPtr);
                        index++;
                    }
                    styleFont[styleName].italic = italic;
                    styleFont[styleName].weight = weight;
                    styleFont[styleName].fontName = fontName;

                    if (defaultStyleName.empty())
                    {
                        defaultStyleName = styleName;
                        DEBUG_SV("默认字体 " << defaultStyleName << endl);
                    }
                    DEBUG_SV(styleName << " => " << italic << " " << weight << " " << fontName << endl);
                }
            }
            else if (state == 3)
            {
                state = 4;
                if (startsWith(line, "Format:"))
                {
                    char *format = line + strlen("Format:");
                    int index = 0;
                    char *tokenSplitPtr = NULL;
                    char *token = strtok_rs(format, ",", &tokenSplitPtr);
                    while (token != NULL)
                    {
                        if (strstr(token, "Style"))
                            eventStyleIndex = index;
                        else if (strstr(token, "Text"))
                            eventTextIndex = index;
                        token = strtok_rs(NULL, ",", &tokenSplitPtr);
                        index++;
                    }
                    DEBUG(" eventStyleIndex, eventTextIndex [%d,%d]\n", eventStyleIndex, eventTextIndex);
                }
                else
                {
                    DEBUG("解析Style格式失败: %s\n", line);
                    return NULL;
                }
            }
            else if (state == 4)
            {
                if (startsWith(line, "Dialogue:"))
                {
                    analyssLine(line);
                }
            }
        }
        // free(code);
        uint32_t resultSize = 4; // 第一位存储item数量
        uint32_t itemCount = 0;
        for (const auto &pair : fontCharList)
        {
            const fontKey &key = pair.first;
            const std::set<uint32_t> &value = pair.second;
            if (value.size() != 0)
            {

                if (fontSubsetRename.find(string_view(key.fontName)) != fontSubsetRename.end())
                {
                    resultSize += (4 + fontSubsetRename[string_view(key.fontName)].size() + 4 + 4 + 4); // name长度 , fontName , weight , italic , valueLen ;
                    resultSize += value.size() * 4;
                    itemCount++;
                }
                else
                {
                    resultSize += (4 + key.fontName.size() + 4 + 4 + 4); // name长度 , fontName , weight , italic , valueLen ;
                    resultSize += value.size() * 4;
                    itemCount++;
                }
            }
        }
        resultSize += 4; // 存储fontSubsetRename数量
        uint32_t subRenameItemCount = 0;
        for (const auto &pair : fontSubsetRename)
        {
            subRenameItemCount++;
            resultSize += (pair.second.size() + 4 + 8); // key固定8字节
        }

        DEBUG("resultSize = %d\n", resultSize);
        DEBUG("itemCount = %d\n", itemCount);
        unsigned char *result = (unsigned char *)malloc(sizeof(unsigned char) * resultSize);
        unsigned char *ptr = result;
        memcpy(ptr, &itemCount, 4);
        ptr += 4;
        for (const auto &pair : fontCharList)
        {
            const fontKey &key = pair.first;
            const std::set<uint32_t> &value = pair.second;
            if (value.size() == 0)
                continue;
            DEBUG_SV("{" << key.fontName << "," << key.weight << "," << key.italic << "}:[");
            string_view fnameRep = fontSubsetRename.find(key.fontName) != fontSubsetRename.end() ? fontSubsetRename[key.fontName] : key.fontName;
            uint32_t nameLen = fnameRep.size();
            memcpy(ptr, &nameLen, 4);
            ptr += 4;
            memcpy(ptr, fnameRep.data(), nameLen);
            ptr += nameLen;

            memcpy(ptr, &key.weight, 4);
            ptr += 4;

            memcpy(ptr, &key.italic, 4);
            ptr += 4;

            uint32_t valueSize = value.size();
            memcpy(ptr, &valueSize, 4);
            ptr += 4;

            for (const uint32_t &val : value)
            {
                DEBUG("%s", uint32ToUnicodeChar(val));
                memcpy(ptr, &val, 4);
                ptr += 4;
            }
            DEBUG("]\n\n");
        }
        memcpy(ptr, &subRenameItemCount, 4);
        ptr += 4;
        for (const auto &pair : fontSubsetRename)
        {
            memcpy(ptr, pair.first.data(), pair.first.size());
            ptr += 8;

            uint32_t nameLen = pair.second.size();
            memcpy(ptr, &nameLen, 4);
            ptr += 4;

            memcpy(ptr, pair.second.data(), pair.second.size());
            ptr += pair.second.size();

            DEBUG_SV("[" << pair.first << " <==> " << pair.second << "]" << endl);
        }
        free(assStr);
        return result;
    }

    void ptrFree(unsigned char *ptr)
    {
        free(ptr);
    }
}

int main()
{
    return 0;
}