function analyseAss(ass_str) {
    const enc = [];
    let currentFontBuffer = [];
    // 找到 [Fonts] 的起始位置
    const fontsSectionStart = ass_str.indexOf('[Fonts]');
    if (fontsSectionStart === -1) {
        return enc;
    }
    // 从 [Fonts] 开始循环
    const fontsContent = ass_str.slice(fontsSectionStart);
    const lines = fontsContent.split('\n');

    for (let i = 1; i < lines.length; i++) {
        const line = lines[i];
        if (line.startsWith('fontname:')) {
            // 遇到新的 fontname 时保存之前的字体内容
            if (currentFontBuffer.length > 0) {
                enc.push(currentFontBuffer.join(''));
            }
            currentFontBuffer = [];
        } else if (line === '') {
            // 空行表示字体内容结束
            if (currentFontBuffer.length > 0) {
                enc.push(currentFontBuffer.join(''));
            }
            break;
        } else {
            currentFontBuffer.push(line);
        }
    }
    //console.log(enc)
    return enc;
}

function uudecode(enc) {
    const OFFSET = 33; // 偏移量
    const binaryData = new Uint8Array(enc.length * 3 / 4); // 预分配空间
    const encoded = new Uint8Array(4);
    let index = 0;
    for (let i = 0; i < enc.length; i += 4) {
        const packed = enc.substring(i, i + 4);
        const packed_length = packed.length;
        // 将字符减去 OFFSET，得到 6 位值
        for (let j = 0; j < packed_length; j++) {
            encoded[j] = packed.charCodeAt(j) - OFFSET;
        }
        // 将 4 个 6 位值还原为 3 个字节
        binaryData[index++] = (encoded[0] << 2) | (encoded[1] >> 4);
        if (packed_length > 2) {
            binaryData[index++] = ((encoded[1] & 0xF) << 4) | (encoded[2] >> 2);
        }
        if (packed_length > 3) {
            binaryData[index++] = ((encoded[2] & 0x3) << 6) | encoded[3];
        }
    }
     // 返回有效部分的 Uint8Array
    return binaryData.slice(0, index);
}


console.log("subtitles-octopus options : \n",options)
if (options.subContent && options.subContent.length > 0){
    options.fonts = analyseAss(options.subContent).map( encodedFont => URL.createObjectURL(new Blob([uudecode(encodedFont)], {type: "font/ttf"})))
}