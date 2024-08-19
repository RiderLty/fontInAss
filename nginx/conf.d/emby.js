import qs from 'querystring';

const debug = (msg) => {
    ngx.log(ngx.ERR, msg);
}

//修改FONT_IN_ASS_SERVER为你的Emby服务器地址
//修改EMBY_SERVER_URL为你的字体处理服务器地址
const FONT_IN_ASS_SERVER = "http://192.168.3.3:8011"
const EMBY_SERVER_URL = "http://127.0.0.1:7096"

const subtitlesHandler = async (r) => {
    const rawResponse = await ngx.fetch(`${EMBY_SERVER_URL}${r.uri}${qs.stringify(r.args) === "" ? "" : "?" + qs.stringify(r.args)}`)
    const rawBytes = await rawResponse.arrayBuffer();
    for (let key in rawResponse.headers) {
        r.headersOut[key] = rawResponse.headers[key]
    }
    try {
        const processedResponse = await ngx.fetch(`${FONT_IN_ASS_SERVER}/process_bytes`, {
            method: 'POST',
            body: rawBytes
        });
        const processedBytes = await processedResponse.arrayBuffer();
        r.headersOut["Content-Length"] = processedBytes.length
        r.return(200, processedBytes);
    } catch (e) {
        r.headersOut["Subtitles-Handler-Error"] = String(e)
        r.return(200, rawBytes);
    }
}

export default { apiHandler, subtitlesHandler };


