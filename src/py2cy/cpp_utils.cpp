#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <ctype.h>
#include <stdbool.h>
#include <iostream>
#include <set>
#include <unordered_map>

using namespace std;

#define startsWith(str, prefix) (strncmp((str), (prefix), strlen(prefix)) == 0)

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
#define DEBUG(...) // 不输出任何信息
#define DEBUG_SV(...)   // 不输出任何信息
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

char *strip(char *str)
{
    if (str == NULL)
    {
        return NULL;
    }

    // 去除开头的空白字符
    char *start = str;
    while (isspace((unsigned char)*start))
    {
        start++;
    }

    // 去除结尾的空白字符
    char *end = str + strlen(str) - 1;
    while (end > start && isspace((unsigned char)*end))
    {
        end--;
    }
    *(end + 1) = '\0'; // 在去除空白字符后的位置添加字符串结束符

    return start;
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
    int italic;
    int weight;
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
        size_t h2 = hash<int>()(fontKey.weight);
        size_t h3 = hash<int>()(fontKey.italic);
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

int nextCode(const char *str, int *index)
// 获取当前code的unicode值，并移动index到下一个开始，返回-1表示结束
{
    unsigned char *s = (unsigned char *)str + *index;
    int unicode = 0;
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

char *intToUnicodeChar(int unicode)
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

extern "C"
{
    unsigned char *analyseAss_CPP(const char *assStr)
    {
        unordered_map<fontKey, set<int>, fontKeyHash> fontCharList;
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
        char *code = (char *)malloc(sizeof(char) * 1024 * 1024);
        for (char *line = strtok_rs((char *)assStr, "\n", &lineSplitPtr); line != NULL; line = strtok_rs(NULL, "\n", &lineSplitPtr))
        {
            DEBUG("line:%s\n", line);
            if (strlen(line) < 1) // 小于最小长度，不用处理
                continue;

            if (state == 0)
            {
                if (startsWith(line, "[V4+ Styles]"))
                {
                    state = 1;
                }
                else if (startsWith(line, "; Font Subset:"))
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
                    int weight = 400;
                    int italic = 0;
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
                            if (atoi(strip(token)) != 0)
                            { // 非0 则是加粗
                                weight = 700;
                            }
                        }
                        else if (index == italicIndex)
                        {
                            italic = atoi(strip(token)) == 0 ? 0 : 1; // 0 则false 其他都为true
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
                        DEBUG_SV(currentFontInfo.italic << " " << currentFontInfo.weight << " " << currentFontInfo.fontName << "未找到，创建新的" << endl);
                        fontCharList[currentFontInfo] = set<int>();
                    }

                    set<int> *currentCharSet = &fontCharList[currentFontInfo];
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
                            memcpy(code, codeStartPtr, codeLen);
                            code[index - codeStart] = '\0';
                            if (startsWith(code, "rnd") && (((strcmp(code + 3, "x") || strcmp(code + 3, "y") || strcmp(code + 3, "z")) && isDigitStr(code + 4)) || (isDigitStr(code + 3))))
                            {
                            }
                            else if (startsWith(code, "p"))
                            {
                                if (codeLen > 1 && isDigitStr(code + 1))
                                    drawMod = atoi(code + 1) != 0;
                            }
                            else if (startsWith(code, "fn"))
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
                            else if (startsWith(code, "r"))
                            {
                                fontKeyChanged = true;
                                string_view rStyleName(codeStartPtr + 1, codeLen - 1);
                                trimLC_strip(rStyleName, '*');
                                if (rStyleName.empty()) // 空的
                                {
                                    currentFontInfo = lineDefaultFontInfo;
                                }
                                else
                                {
                                    if (styleFont.find(rStyleName) == styleFont.end())
                                        currentFontInfo = lineDefaultFontInfo;
                                    else
                                        currentFontInfo = styleFont[rStyleName];
                                }
                                DEBUG_SV("style切换" << rStyleName << endl);
                            }
                            else if (startsWith(code, "b"))
                            {
                                fontKeyChanged = true;
                                if (codeLen == 1)
                                {
                                    currentFontInfo.weight = lineDefaultFontInfo.weight;
                                }
                                else if (isDigitStr(code + 1))
                                {
                                    int bold = atoi(code + 1);
                                    if (bold == 0)
                                        currentFontInfo.weight = 400;
                                    else if (bold == 1)
                                        currentFontInfo.weight = 700;
                                    else
                                        currentFontInfo.weight = bold;
                                }
                            }
                            else if (startsWith(code, "i")) //
                            {
                                fontKeyChanged = true;
                                if (codeLen == 1)
                                    currentFontInfo.italic = lineDefaultFontInfo.italic;
                                else if (isDigitStr(code + 1))
                                    currentFontInfo.italic = currentFontInfo.italic == 0 ? 0 : 1;
                            }
                        }
                        if (fontKeyChanged)
                        {
                            if (fontCharList.find(currentFontInfo) == fontCharList.end())
                            {
                                DEBUG_SV(currentFontInfo.italic << " " << currentFontInfo.weight << " " << currentFontInfo.fontName << "未找到，创建新的" << endl);
                                fontCharList[currentFontInfo] = set<int>();
                            }
                            currentCharSet = &fontCharList[currentFontInfo];
                        }
                        if (addChar)
                        {
                            int unicode = nextCode(text, &index);
                            if (unicode != '\r')
                            {
                                DEBUG_SV(currentFontInfo.fontName << "\t" << currentFontInfo.weight << "\t" << currentFontInfo.italic << ":" << intToUnicodeChar(unicode) << "(" << unicode << ")" << endl);
                                currentCharSet->insert(unicode);
                            }
                        }
                        else
                        {
                            index++;
                        }
                    }
                    DEBUG("\n\n");
                }
            }
        }
        free(code);
        int resultSize = 4; // 第一位存储item数量
        int itemCount = 0;
        for (const auto &pair : fontCharList)
        {
            const fontKey &key = pair.first;
            const std::set<int> &value = pair.second;
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
        int subRenameItemCount = 0;
        for (const auto &pair : fontSubsetRename)
        {
            subRenameItemCount++;
            resultSize += (pair.second.size() + 4 + 8); // key固定8字节
        }

        DEBUG("resultSize = %d\n", resultSize);
        DEBUG("itemCount = %d\n", itemCount);
        unsigned char *result = (unsigned char *)malloc(sizeof(unsigned char) * resultSize);
        unsigned char *ptr = result;
        memcpy(ptr, &itemCount, sizeof(int));
        ptr += sizeof(int);
        for (const auto &pair : fontCharList)
        {
            const fontKey &key = pair.first;
            const std::set<int> &value = pair.second;
            if (value.size() == 0)
                continue;
            DEBUG_SV("{" << key.fontName << "," << key.weight << "," << key.italic << "}:[");
            string_view fnameRep = fontSubsetRename.find(key.fontName) != fontSubsetRename.end() ? fontSubsetRename[key.fontName] : key.fontName;
            int nameLen = fnameRep.size();
            memcpy(ptr, &nameLen, sizeof(int));
            ptr += sizeof(int);
            memcpy(ptr, fnameRep.data(), nameLen);
            ptr += nameLen;

            memcpy(ptr, &key.weight, sizeof(int));
            ptr += sizeof(int);

            memcpy(ptr, &key.italic, sizeof(int));
            ptr += sizeof(int);

            int valueSize = value.size();
            memcpy(ptr, &valueSize, sizeof(int));
            ptr += sizeof(int);

            for (const int &val : value)
            {
                DEBUG("%s", intToUnicodeChar(val));
                memcpy(ptr, &val, sizeof(int));
                ptr += sizeof(int);
            }
            DEBUG("]\n\n");
        }
        memcpy(ptr, &subRenameItemCount, sizeof(int));
        ptr += sizeof(int);
        for (const auto &pair : fontSubsetRename)
        {
            memcpy(ptr, pair.first.data(), pair.first.size());
            ptr += 8;

            int nameLen = pair.second.size();
            memcpy(ptr, &nameLen, sizeof(int));
            ptr += sizeof(int);

            memcpy(ptr, pair.second.data(), pair.second.size());
            ptr += pair.second.size();

            DEBUG_SV("[" << pair.first << " <==> " << pair.second << "]" << endl);
        }
        return result;
    }

    void ptrFree(unsigned char *ptr)
    {
        free(ptr);
    }
}


int main(){
    return 0;
}