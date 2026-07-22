local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false

local BaseAnim = BaseAnim or {}

function BaseAnim:new()
    local obj = {  }
    setmetatable(obj, self)
    self.__index = self
    -------------变量----------------
    self.text = nil --sdftext
    self.rich_text = nil --text
    self.comp = nil 
    self.parentTrans = nil
    self.textEntity = nil

    self.baseTest = "1"
    self.initStyleInfo = {
        richColor = {},
        fontSize = {},
        backGroundEnable = false,
        outLineEnable = false,
        lineGap = 0,
        wordGap = 0,
        shadowEnable = false,
        BloomPath = "",
        typeSettingKind = 0,
        textAlign = 0, 
    }

    
    self.runningStyleInfo = {
        textColor =  Amaz.Vector3f(1.0,1.0,1.0),
        fontSize = 22,
        backGroundEnable = false,
        outLineEnable = false,
        lineGap = 0,
        wordGap = 0,
        shadowEnable = false,
        BloomPath = "",
        typeSettingKind = 0,
        textAlign = 0, 
    }

    -----------------字幕动画属性--------------------
    self.subTitlesAnimType = -1
    self.textTimeData = {} --字幕动画时序信息
    self.subTitlesProgress = 0 --字幕动画时间周期

    self.runningCharInfo = {
        chars = {},---生效的单词字符
        beginIndex = 0, --生效的单词起始下标
        endIndex = 0 --生效单词结尾下标
    }

    -------------------clone对象管理-----------------
    self.cloneEntity = {}
	self.cloneEntityRenderer = {}
    self.cloneEffectLayers = {}
    self.cloneEffectParams = {}
    self.ctrans = {}
    self.cloneMaterial={} --clone的材质
    self.cloneText = {} --sdf对象
    self.clone_richText = {} --富文本对象
    ----------工具util对象-----------------
    self.util = includeRelativePath("Util")
    return obj
end


function BaseAnim:seek(time)
    local str = self.text.str
    for i, value in pairs(self.cloneText) do
        self.cloneText[i].str=str
        self.cloneText[i]:forceTypeSetting()
    end

    --------更新字幕动画显示逻辑--------
    if isEditor then
        self:ReadFromJson("")
    end
    self:updateSubTitlesAnim(time)
end


function BaseAnim:refreshRunningStyle()
    local org_str = self.text.str
    local letterColor = self:getTextColor()
    local font_size = self:getFontSize()
    local background_state = self:getBackGroundEnabled()
    local outline_state = self:getTextOutlineEnabled()
    local shadow_state = self:getTextShadowEnabled()
    local line_gap = self.text.lineGap
    local word_gap = self.text.wordGap
    local type_setting = self.text.typeSettingKind
    local text_align = self.text.textAlign
    local bloom_path = self.rich_text.BloomPath or self.rich_text.bloomPath
    self.runningStyleInfo = {
        str = org_str,
        richColor = letterColor,
        fontSize = font_size,
        backGroundEnable = background_state,
        outLineEnable = outline_state,
        lineGap = line_gap,
        wordGap = word_gap,
        shadowEnable = shadow_state,
        BloomPath = bloom_path,
        typeSettingKind = type_setting,
        textAlign = text_align, 
    }
    
end

function BaseAnim:initData()
    local org_str = self.text.str
    local letterColortab = {}
    local fontSizetab = {}
    for i = 1, self.rich_text.letters:size() do
        local letter = self.rich_text.letters:get(i-1)
        if letter and letter.letterStyle and letter.letterStyle.letterColor then 
            table.insert(letterColortab,letter.letterStyle.letterColor)
        end
    end

    for i = 1, self.rich_text.letters:size() do
        local letter = self.rich_text.letters:get(i-1)
        if letter and letter.letterStyle and letter.letterStyle.fontSize then 
            table.insert(fontSizetab,letter.letterStyle.fontSize)
        end
    end

    local background_state = self:getBackGroundEnabled()
    local outline_state = self:getTextOutlineEnabled()
    local shadow_state = self:getTextShadowEnabled()
    local line_gap = self.text.lineGap
    local word_gap = self.text.wordGap
    local type_setting = self.text.typeSettingKind
    local text_align = self.text.textAlign
    local bloom_path = self.rich_text.BloomPath or self.rich_text.bloomPath

    self.initStyleInfo = {
        str = org_str,
        richColor = letterColortab,
        fontSize = fontSizetab,
        backGroundEnable = background_state,
        outLineEnable = outline_state,
        lineGap = line_gap,
        wordGap = word_gap,
        shadowEnable = shadow_state,
        BloomPath = bloom_path,
        typeSettingKind = type_setting,
        textAlign = text_align, 
    }
end

function BaseAnim:init(comp)
    self.comp = comp
    Amaz.LOGI("BaseAnim===",tostring(self))
    self.text = comp.entity:getComponent('SDFText')
    self.rich_text = comp.entity:getComponent('Text')
    self.trans = comp.entity:getComponent('Transform')
    self.parentTrans = self.trans.parent
    self.textEntity=comp.entity
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
            self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    --确保首帧拿到正确的chars:chout,rowth信息
    self.text:forceTypeSetting() 
    self:initData() --记录样式初始值
end


---------------------------样式设置接口--------------------------------
--包括发光后的RTSize
function BaseAnim:getMainSize()
    local expandSize = self:getExpandedSize()
    local mSize = expandSize
    if self.text.textWrapper and self.text.textWrapper.bloomRtSize  then
        if self.text.textWrapper.bloomRtSize.x > expandSize.width then
            mSize = Amaz.Vector2f(self.text.textWrapper.bloomRtSize.x,self.text.textWrapper.bloomRtSize.y)
        end
    end
    
    if self.text.textWrapper and self.text.textWrapper.BloomRtSize  then
        if self.text.textWrapper.BloomRtSize.x > expandSize.width then
            mSize = Amaz.Vector2f(self.text.textWrapper.BloomRtSize.x,self.text.textWrapper.BloomRtSize.y)
        end
    end
    return mSize
end

--获得当前文本渲染区的RT大小（不包含发光）
function BaseAnim:getExpandedSize()
    local rt_width = (self.text:getRectExpanded().width + self.text.targetRTExtraSize.x) * self.trans.parent.localScale.x
    local rt_height = (self.text:getRectExpanded().height + self.text.targetRTExtraSize.y) * self.trans.parent.localScale.y
    return {width = rt_width,height = rt_height}
end

--获得当前有多少行
function BaseAnim:getTextLineCount()
    local line_row = 0
	local len = self.text.chars:size()
	for i = 1, len do
		local char = self.text.chars:get(i - 1)
        if char.rowth > line_row then
            line_row = char.rowth
        end
	end
    return line_row + 1
end

---获得字体颜色
function BaseAnim:getTextColor()
    local text = self.rich_text
    local textColor = Amaz.Vector3f(1.0, 1.0, 1.0)
    if text then 
        local letters = text.letters
        if letters:size() > 0 then
            local letter0 = letters:get(0)
            textColor = letter0 and letter0.letterStyle and letter0.letterStyle.letterColor
        end
    else
        textColor = self.text.textColor
    end
    return textColor
end

--设置富文本颜色
function BaseAnim:setRichTextColor(color)
    local text = self.rich_text
    if text then
        for i = 1, self.rich_text.letters:size() do
            local letter = self.rich_text.letters:get(i-1)
            if letter and letter.letterStyle and letter.letterStyle.letterColor then 
                letter.letterStyle.letterColor = Amaz.Vector3f(color.x, color.y, color.z)
            end
        end
    end
end

--获得字号
function BaseAnim:getFontSize()
    local letters = self.rich_text.letters
    local fontsize = 8
    if letters:size() > 0 then
        local letter0 = letters:get(0)
        fontsize = letter0.letterStyle.fontSize
    end
    return fontsize
end

--设置字号
function BaseAnim:setFontSize(font_size)
    self.running_font_size = font_size
    local text = self.rich_text
    if text then
        for i = 1, self.rich_text.letters:size() do
            local letter = self.rich_text.letters:get(i-1)
            if letter and letter.letterStyle and letter.letterStyle.fontSize then 
                letter.letterStyle.fontSize = font_size
            end
        end
    end
end

--设置是否显示背景色
function BaseAnim:setBackGroundEnabled(enable_state)
    self.text.backgroundEnabled = enable_state
end

--获得背景状态
function BaseAnim:getBackGroundEnabled()
    return self.text.backgroundEnabled
end

--修改字符串
function BaseAnim:setTextStr(str)
    self.running_str = str --低版本兼容判断所用
    self.text.str = str
    self.text:forceTypeSetting()
end

--获得文字阴影状态接口
function BaseAnim:getTextShadowEnabled()
    local text = self.rich_text
    local state = false
    if text then 
        local letters = text.letters
        if letters:size() > 0 then
            local letter0 = letters:get(0)
            state = letter0 and letter0.letterStyle and letter0.letterStyle.shadowEnabled
        end
    else
        state = self.text.shadowEnabled
    end
    return state
end


function BaseAnim:setTextShadowEnabled(state)
    local text = self.rich_text
    if text then
        for i = 1, text.letters:size() do
            local letter = text.letters:get(i-1)
            if letter then
                if letter.letterStyle then
                    letter.letterStyle.shadowEnabled = state
                end
            end
        end
    end
end

----描边层状态
function BaseAnim:getTextOutlineEnabled()
    local text = self.rich_text
    local state = false
    if text then 
        local letters = text.letters
        if letters:size() > 0 then
            local letter0 = letters:get(0)
            state = letter0 and letter0.letterStyle and letter0.letterStyle.outlineEnabled
        end
    else
        state = self.text.outlineEnabled
    end
    return state
end

function BaseAnim:setOutLineEnabled(state)
    local text = self.rich_text
    if text then 
        local letters = text.letters
        if letters:size() > 0 then
            local letter0 = letters:get(0)
            if letter0 then
                if letter0.letterStyle then
                    letter0.letterStyle.outlineEnabled = state
                end
            end
        end
    else
        self.text.outlineEnabled = state
    end
end

--设置发光状态
function BaseAnim:setBloomEnabled(state)
    local text = self.rich_text
    if state and self.initStyleInfo.BloomPath then
        if text.BloomPath then
            text.BloomPath = self.initStyleInfo.BloomPath 
        elseif text.bloomPath then
            text.bloomPath = self.initStyleInfo.BloomPath 
        end
    else
        if text.BloomPath then
            text.BloomPath = ""
        elseif text.bloomPath then
            text.bloomPath = ""
        end
    end
end


-----------------------------字幕动画---------------------------------
function BaseAnim:ReadFromJson(jsondata)
    local jsonData = self.util.ReadFromJson("data_val.json", jsondata)
    self.textTimeData = jsonData
end
--字幕动画单词时间接收接口
function BaseAnim:onSetProperty(key, value)
    if key == "caption_duration_info" and value ~= "" then
        self:ReadFromJson(value)
    end
end
---单词显示类型（0:从左到右显示，1:居中显示）
function BaseAnim:setSubTitlesAnimType(a_type)
    self.subTitlesAnimType = a_type
end

local function GetStringWordNum(str)
    local lenInByte = #str
    local count = 0
    local i = 1
    while true do
        local curByte = string.byte(str, i)
        if i > lenInByte then
            break
        end
        local byteCount = 1
        if curByte > 0 and curByte < 128 then
            byteCount = 1
        elseif curByte>=128 and curByte<224 then
            byteCount = 2
        elseif curByte>=224 and curByte<240 then
            byteCount = 3
        elseif curByte>=240 and curByte<=247 then
            byteCount = 4
        else
            break
        end
        -- local char = string.sub(str, i, i+byteCount-1)
        i = i + byteCount
        count = count + 1
    end
    return count
end

function BaseAnim:updateTimeData(time)
    local my_textTimeData = {
        ["words"] = {}
    }
    local cur_text_length = 1
    for i = 1, #self.textTimeData.words do
        local words = self.textTimeData.words[i]
        local text_len = GetStringWordNum(words.text)
        local chars = {}
        local extra = {
            ["center"] = Amaz.Vector2f(0,0)
        }
        local tmp_sum_point = Amaz.Vector2f(0,0)
        for j = cur_text_length, cur_text_length + text_len - 1 do
            local char = self.text.chars:get(j-1)
            local ori_pos = char.initialPosition
            tmp_sum_point = Amaz.Vector2f(
                tmp_sum_point.x + ori_pos.x,
                tmp_sum_point.y + ori_pos.y
            )
            table.insert(chars, char)
        end

        extra["center"] = Amaz.Vector2f(
            tmp_sum_point.x/#chars, 
            tmp_sum_point.y/#chars
        )

        local tmpt = {
            ["start_time"] = words.start_time,
            ["text"] = words.text,
            ["end_time"] = words.end_time,
            ["begin_index"] = cur_text_length,
            ["end_index"] =  cur_text_length + text_len - 1,
            ["chars"] = chars,
            ["extra"] = extra
        }
        cur_text_length = cur_text_length + text_len

        table.insert(my_textTimeData["words"], tmpt)
    end

    local runningchars = {}
    local begin_index = 9999
    local end_index  = 0
    for i = 1, #my_textTimeData.words do
        local words = my_textTimeData.words[i]
        local start_time = words.start_time
        local end_time = words.end_time
        local t = time * 1000
        local chars = words.chars
        if t >= start_time and t < end_time then
            --防止同时间段多单词
            begin_index = words.begin_index < begin_index and words.begin_index or begin_index
            end_index = words.end_index > end_index and words.end_index or end_index 
            for j = 1, #chars do
                local char = chars[j]
                table.insert(runningchars,char)
            end
            local duration = end_time-start_time
            duration = duration <= 0 and 0.0001 or duration
            local pt = (t-start_time)/duration
            self.subTitlesProgress = self.util.clamp(0,1,pt)
        end
    end
    self.runningCharInfo = {chars = runningchars,beginIndex = begin_index,endIndex = end_index}
    self.my_textTimeData = my_textTimeData
end

function BaseAnim:updateWordByWord(time)
    local my_textTimeData = self.my_textTimeData 
    for i = 1, #my_textTimeData.words do
        local words = my_textTimeData.words[i]
        local start_time = words.start_time
        local end_time = words.end_time
        local chars = words.chars
        local t = time * 1000
        if t >= start_time  then
            for j = 1, #chars do
                local char = chars[j]
                char.scale = Amaz.Vector3f(1,1,1)
            end
        else
            for j = 1, #chars do
                local char = chars[j]
                char.scale = Amaz.Vector3f(0,0,0)
            end
        end

    end
end

function BaseAnim:updateWordToCenter(time)
    local my_textTimeData = self.my_textTimeData 
    for i = 1, #my_textTimeData.words do
        local words = my_textTimeData.words[i]
        local start_time = words.start_time
        local end_time = words.end_time
        local chars = words.chars
        local extra = words.extra
        local t = time * 1000
        if t >= start_time and t < end_time then
            for j = 1, #chars do
                local char = chars[j]
                char.scale = Amaz.Vector3f(1,1,1)
                local ori_pos = char.initialPosition
                char.position = Amaz.Vector3f(
                    ori_pos.x - extra["center"].x,
                    ori_pos.y - extra["center"].y,
                    0
                )
            end
        else
            for j = 1, #chars do
                local char = chars[j]
                char.scale = Amaz.Vector3f(0,0,0)
            end
        end

    end
end

--刷新字幕动画字符显示信息
function BaseAnim:updateSubTitlesAnim(time)
    self:updateTimeData(time) --组装时序
    if self.subTitlesAnimType == 0 then --逐单词显示
        self:updateWordByWord()
    elseif self.subTitlesAnimType == 1 then --剧中显示
        self:updateWordToCenter(time)
    end
end

----获得正在播放的单词
function BaseAnim:getRunningCharInfo()
    return self.runningCharInfo
end

function BaseAnim:getSubTitleProgress(time)
    return self.subTitlesProgress
end


-------------------------clone函数实现--------------------------------------
function BaseAnim:getLayer()
    self.entities = self.text.entity.scene.entities
    local layer = 1
    for i = 0, self.entities:size() - 1 do
        local e = self.entities:get(i)
        local trans = self.trans
        local entityname = ""
        while trans ~= nil  do
            if trans.entity.name ~= "" then
                entityname = trans.entity.name
                break
            end
            trans = trans.parent
        end
        if entityname == e.name then
            layer = i
            break
        end
    end
    return layer
end

function BaseAnim:setMatToSDFText(i,text, rendermaterial,clonematerial)
    text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if clonematerial then
        InsMaterials = clonematerial:instantiate()
    end
    materials:pushBack(InsMaterials)
    self.cloneMaterial[i] = materials
    materials.renderQueue = 0 --设置渲染层级在下层，规避下划线，阴影切换层级异常问题
    rendermaterial.materials = materials
    return rendermaterial.material
end

function BaseAnim:addEffectLayers(i)
	if self.text.effectTextParam ~= nil then
    	self.effectLayers = self.text.effectTextParam.effectLayers
	else
		return 
	end
	self.cloneEffectParams[i] = self.cloneEntity[i]:getComponent("SDFText").effectTextParam
	if self.cloneEffectParams[i] ~= nil and self.effectLayers ~= nil then
		self.cloneEffectLayers[i] = self.cloneEffectParams[i].effectLayers
		for j = 0, self.cloneEffectLayers[i]:size() - 1 do 
			if j < self.effectLayers:size() then
				self.cloneEffectLayers[i]:get(j).mat = self.effectLayers:get(j).mat
				self.cloneEffectLayers[i]:get(j).texture = self.effectLayers:get(j).texture
			end
		end
	end
end

function BaseAnim:addEntity(i)

    Amaz.LOGI("dkdkkdkdkdk",tostring(self))
	if self.cloneEntity[i]==nil then
		self.cloneEntity[i] = self.textEntity.scene:createEntity("sdf"..i)
		self.cloneEntity[i]:addComponent("Transform")
		self.ctrans[i] = self.cloneEntity[i]:getComponent("Transform")
		self.ctrans[i].localPosition = Amaz.Vector3f(0.0, 0.0, -10.0)
        self.ctrans[i].localScale = Amaz.Vector3f(1, 1, 1.0)
		if self.rich_text then
            self.clone_richText[i] = self.cloneEntity[i]:cloneComponentOf(self.rich_text)
		end
		self.cloneEntity[i]:cloneComponentOf(self.text)
		self.cloneEntity[i]:cloneComponentOf(self.renderer)
        self.cloneText[i]=self.cloneEntity[i]:cloneComponentOf(self.text)
        if self.clone_richText[i] then
			self.cloneText[i]:setTextWrapper(self.clone_richText[i])
		end
		self.cloneText[i].str=self.originText 
		self.cloneText[i].backgroundColor = Amaz.Vector4f(0,0,0,0)
		self.cloneText[i]:forceTypeSetting()
		self.ctrans[i].parent = self.parentTrans
		if self.parentTrans then
			self.parentTrans.children:pushBack(self.ctrans[i])
		end
		self:addEffectLayers(i)
	end
end

function BaseAnim:clone(_material)
    local count = #self.cloneEntity
    count = count + 1
    self:addEntity(count)
    local sdf = self.cloneEntity[count]:getComponent("SDFText")
    local mesh = self.cloneEntity[count]:getComponent("MeshRenderer")
    self:setMatToSDFText(count, sdf,mesh,_material)
    local order_index =1 
    local layer = self:getLayer()
    if self.trans.parent then
        order_index = order_index*10
        local parent_idx=layer*order_index
        self.cloneEntityRenderer[count].autoSortingOrder=false
        self.cloneEntityRenderer[count].sortingOrder=self.renderer.sortingOrder+count
        self.cloneEntityRenderer[count].sortingOrder=parent_idx+count
    else
        self.cloneEntityRenderer[count].autoSortingOrder=true
    end
    self.cloneText[count].renderToRT=true
    return self.cloneEntity[count]
end


local getVersionNum = function(sdk_str)
    local sp_str = "."
    local splits = {}
    local sdk_version_num = 0
    if sdk_str and sdk_str ~= "" then
        -- normal split use gmatch
        local pattern = "[^" .. sp_str .. "]+"
        for str in string.gmatch(sdk_str, pattern) do
            table.insert(splits, str)
        end
    end
    local len = #splits
    local m_num = 10
    for i=len,1,-1 do
        sdk_version_num = sdk_version_num + tonumber(splits[i])*m_num
        m_num = m_num * 10
    end
    return sdk_version_num
end


--------------------Tween动画接口------------------------
function BaseAnim:createTween()

end
------------------loadprefab----------------------------
function BaseAnim:loadPrefab(prefab)

end

---------------------------状态管理接口-------------------
function BaseAnim:resetStyle()
    ----1410版本以后时序调整了
    if getVersionNum(EffectSdk.getSDKVersion())>= getVersionNum("14.1.0") then
        self.text.str = self.initStyleInfo.str
        for i = 1, self.rich_text.letters:size() do
            local letter = self.rich_text.letters:get(i-1)
            if letter and letter.letterStyle and letter.letterStyle.letterColor then 
                letter.letterStyle.letterColor = self.initStyleInfo.richColor[i]
            end
        end
        for i = 1, self.rich_text.letters:size() do
            local letter = self.rich_text.letters:get(i-1)
            if letter and letter.letterStyle and letter.letterStyle.fontSize then 
                letter.letterStyle.fontSize = self.initStyleInfo.fontSize[i]
            end
        end

    else
        local cur_fontsize = self:getFontSize()
        if cur_fontsize == self.runningStyleInfo.fontSize then --用户没有设置
            for i = 1, self.rich_text.letters:size() do
                local letter = self.rich_text.letters:get(i-1)
                if letter and letter.letterStyle and letter.letterStyle.letterColor then 
                    letter.letterStyle.letterColor = self.initStyleInfo.richColor[i]
                end
            end
        end
        local cur_color = self:getTextColor()
        local running_color = self.runningStyleInfo.textColor 
        if math.abs(cur_color.x-running_color.x) + math.abs(cur_color.y-running_color.y)+ math.abs(cur_color.z-running_color.z) < 0.01 then
            for i = 1, self.rich_text.letters:size() do
                local letter = self.rich_text.letters:get(i-1)
                if letter and letter.letterStyle and letter.letterStyle.fontSize then 
                    letter.letterStyle.fontSize = self.initStyleInfo.fontSize[i]
                end
            end
        end
    end
    self.text.backgroundEnabled = self.initStyleInfo.backGroundEnable
    self:setOutLineEnabled(self.initStyleInfo.outLineEnable)
    self:setTextShadowEnabled(self.initStyleInfo.shadowEnable)
    self.text.lineGap =self.initStyleInfo.lineGap
    self.text.wordGap = self.initStyleInfo.wordGap
    self.text.typeSettingKind = self.initStyleInfo.typeSettingKind
    self.text.textAlign = self.initStyleInfo.textAlign
    if self.rich_text.bloomPath then
        self.rich_text.bloomPath = self.initStyleInfo.BloomPath
    end
    if self.rich_text.BloomPath then
        self.rich_text.BloomPath = self.initStyleInfo.BloomPath
    end
end

function BaseAnim:resetData( ... )
	if not self.text then
        return
    end
    local chars = self.text.chars 
    for i = 1, self.text.chars:size() do
        local char = chars:get(i - 1)
        if char.rowth ~= -1 then
            char.position = char.initialPosition
            char.rotate = Amaz.Vector3f(0, 0, 0)
            char.scale = Amaz.Vector3f(1, 1, 1)
            char.color = Amaz.Vector4f(1, 1, 1, 1)
        end
    end

    self.text.renderToRT = false --恢复普通文本渲染流程
    self.text.chars = chars
    self.text.targetRTExtraSize = Amaz.Vector2f(0.0, 0.0) --复原RTSize
    self:resetStyle()--恢复样式

    for i, value in pairs(self.cloneEntity) do
        self.textEntity.scene:removeEntity(self.cloneEntity[i])
        if self.parentTrans.children:size() > 1 and self.cloneEntity[i] then
            self.parentTrans.children:erase(self.cloneEntity[i])
        end
        self.cloneEntity[i] = nil
    end
    self.cloneEntity = {}
end

function BaseAnim:onLeave()
    self:resetData()
end

function BaseAnim:clear()
    self:resetData()
end

function BaseAnim:onEnter()
    self.first = true
end


return BaseAnim
