from hoshino import Service
from hoshino.priv import *
from nonebot import *
import json
from os import path

_bot = get_bot()

sv = Service("转发广告杀手")

Inited = False
StrictMode = False
PunishMode = False
SenderReplace = False
BanWord = []
StrictBanWord = []
ArrayReportMode = False

def init():
    global Inited
    global StrictMode
    global PunishMode
    global SenderReplace
    global BanWord
    global StrictBanWord
    config_path = path.join(path.dirname(__file__),'config.json')
    with open(config_path,'r',encoding='utf8')as fp:
        conf = json.load(fp)
        StrictMode = conf['enable_strict_mode']
        PunishMode = conf['enable_punish_mode']
        SenderReplace = conf['enable_fake_sender']
        BanWord = conf['ban_word']
        StrictBanWord = conf['strict_ban_word']
    Inited = True

def build_send_forward_message(originMsg):
    sendMsg = []
    for node in originMsg:
        data = {
            "type": "node",
            "data": {
                "name": str(node['sender']['nickname']),
                "uin": str(node['sender']['user_id']),
                "content": node['content']
            }
        }
        sendMsg.append(data)
    return sendMsg

async def exact_forward_message(msgcq):
    startIndex=msgcq.find("id=") + 3
    endIndex=msgcq.find("]")
    msgId=msgcq[startIndex:endIndex]
    return await _bot.get_forward_msg(message_id=msgId) #Waring message_id为go-cqhttp AIP字段，onebot内为id，反馈后后续版本会统一

async def get_inner_forward_message_id(ctx,fmsgid):
    fmsg = await _bot.get_forward_msg(message_id=fmsgid)
    nfmsg = get_ad_removed_message(ctx,fmsg)
    smsg = build_send_forward_message(nfmsg)
    msgId = await _bot.send_group_forward_msg(group_id=ctx['group_id'], messages=smsg)
    #sv.logger.info("new forward message id:"+msgId)
    self_id = ctx['self_id']
    #await _bot.delete_msg(self_id=self_id, message_id=msgId)
    return '[CQ:forward,id={msg_id}]'.format(msg_id=msgId)

async def get_ad_removed_message(ctx,fmsg):
    global ArrayReportMode
    have_ad = False
    #fmsg = fmsg.copy()
    msgLen = len(fmsg)
    msgStart = msgLen-5
    cutIndex = msgLen - 1
    if msgStart < 0:
        msgStart=0
    for i in range(0,msgLen):
        innerMsg = fmsg[i]['content']
        if not ArrayReportMode and isinstance(innerMsg,list):
            ArrayReportMode = True
        if ArrayReportMode and isinstance(innerMsg,str):
            ArrayReportMode = False
        if ArrayReportMode:
            if innerMsg[0]['type'] == 'text':
                if '[合并转发]' in innerMsg[0]['data']['text']:
                    return fmsg
        else:
            if "&#91;合并转发&#93" in innerMsg:
                #  目前版本的go-cqhttp拿不到合并转发的套娃消息，因此暂时只支持一层
                #    innerMsg = await get_inner_forward_message_id(ctx,innerMsg)
                return fmsg
    for i in range(msgStart,msgLen):
        if have_ad:
            break
        innerMsg = fmsg[i]['content']
        if ArrayReportMode:
            for msg in innerMsg:
                if msg['type'] == 'text':
                    textmsg = msg['data']['text']
                    for word in BanWord:
                        if word in textmsg:
                            have_ad = True
                            cutIndex = i
                    if StrictMode:
                        for word in StrictBanWord:
                            if word in textmsg:
                                have_ad = True
                                cutIndex = i
        else:
            for word in BanWord:
                if word in innerMsg:
                    have_ad = True
                    cutIndex = i
            if StrictMode:
                for word in StrictBanWord:
                    if word in innerMsg:
                        have_ad = True
                        cutIndex = i
    if have_ad:
        buildMsg = []
        for i in range(0,cutIndex):
            if SenderReplace:
                fmsg[i]['sender']['nickname'] = ctx['sender']['nickname']
                fmsg[i]['sender']['user_id'] = ctx['sender']['user_id']
            buildMsg.append(fmsg[i])
        if PunishMode:
            if ArrayReportMode:
                buildMsg.append({
                    "content" : [{'data': {'text': '再转发有广告的消息我就是小猪'}, 'type': 'text'}],
                    "sender" : {
                        "nickname" : ctx['sender']['nickname'],
                        "user_id" : ctx['sender']['user_id'],
                        "time" : ctx['time']
                    }
                })
                pass
            else:
                buildMsg.append({
                    "content" : "再转发有广告的消息我就是小猪",
                    "sender" : {
                        "nickname" : ctx['sender']['nickname'],
                        "user_id" : ctx['sender']['user_id'],
                        "time" : ctx['time']
                    }
                })
        fmsg = buildMsg
    return {"msg":fmsg,"have_ad":have_ad}

@sv.on_fullmatch('重载转发广告杀手配置')
async def reload_config(bot, ev):
    if check_priv(ev, SUPERUSER):
        init()
        await bot.send(ev, '重新载入配置文件成功')
    else:
        await bot.send(ev, '仅SUPERUSER能够使用该指令哦')

@sv.on_message()
async def on_message_process(*params):
    if not Inited:
        init()
    bot, ctx = (_bot, params[0]) if len(params) == 1 else params
    #sv.logger.info(ctx)
    msg = str(ctx['message']).strip()
    sv.logger.info(msg)
    if 'CQ:forward' in msg:
        fmsg = await exact_forward_message(msg)
        sv.logger.info(fmsg)
        fmsg = fmsg['messages']
        fmsg = await get_ad_removed_message(ctx,fmsg)
        if not fmsg["have_ad"]:
            return
        else:
            try:
                await _bot.delete_msg(self_id=ctx['self_id'], message_id=ctx['message_id'])
            except:
                return
            fmsg = fmsg["msg"]
        smsg = build_send_forward_message(fmsg)
        await bot.send_group_forward_msg(group_id=ctx['group_id'], messages=smsg)


