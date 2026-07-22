local isEditor = (Amaz.Macros and Amaz.Macros.EditorSDK) and true or false
local exports = exports or {}
local AnimScript = AnimScript or {}

---@class AnimScript : ScriptComponent
---@field duration number
---@field progress number [UI(Range={0.0, 1.0}, Slider)]
---@field auto_play boolean
---@field effect_material Material
---@field clone_material Material

local ANIMATIONTYPE = {
    IN = 1, 
    OUT = 2,
    LOOP = 3, 
    SUBTITLE = 4 
}

local SUBANIMTYPE = {
    CHAR = 1, 
    WORD = 2, 
    LINE = 3 
}

local ae_attribute = {
	["ADBE_Scale_0_0"]={
		{{0.053093827,0.33333333,0.33333333, -0.001375441,0.33333333,0.33333333, 0.425349219,0.66666667,0.66666667, 1,0.66666667,0.66666667, }, {2, 10, }, {{310, 100, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["ADBE_Opacity_0_1"]={
		{{0.053093827, 0.002166319, 0.425349219, 1, }, {1, 7, }, {{0, }, {100, }, }, }, 
	}, 
	["ADBE_Scale_1_2"]={
		{{0.053093827,0.33333333,0.33333333, -0.001375441,0.33333333,0.33333333, 0.425349219,0.66666667,0.66666667, 1,0.66666667,0.66666667, }, {6, 14, }, {{310, 100, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["ADBE_Opacity_1_3"]={
		{{0.041616963, 0.001698043, 0.344910069, 1, }, {5, 11, }, {{0, }, {100, }, }, }, 
	}, 
	["ADBE_Scale_2_4"]={
		{{0.053093827,0.33333333,0.33333333, -0.001375441,0.33333333,0.33333333, 0.425349219,0.66666667,0.66666667, 1,0.66666667,0.66666667, }, {10, 18, }, {{310, 100, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["ADBE_Opacity_2_5"]={
		{{0.041616963, 0.001698043, 0.344910069, 1, }, {9, 15, }, {{0, }, {100, }, }, }, 
	}, 
	["ADBE_Scale_3_6"]={
		{{0.053093827,0.33333333,0.33333333, -0.001375441,0.33333333,0.33333333, 0.425349219,0.66666667,0.66666667, 1,0.66666667,0.66666667, }, {14, 22, }, {{310, 100, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["ADBE_Opacity_3_7"]={
		{{0.041616963, 0.001698043, 0.344910069, 1, }, {13, 19, }, {{0, }, {100, }, }, }, 
	}, 
	["ADBE_Scale_4_8"]={
		{{0.053093827,0.33333333,0.33333333, -0.001375441,0.33333333,0.33333333, 0.425349219,0.66666667,0.66666667, 1,0.66666667,0.66666667, }, {18, 26, }, {{310, 100, 100, }, {100, 100, 100, }, }, }, 
	}, 
	["ADBE_Opacity_4_9"]={
		{{0.041616963, 0.001698043, 0.344910069, 1, }, {17, 23, }, {{0, }, {100, }, }, }, 
	}, 
}


local ae_attribute1 = {
	["ADBE_Gaussian_Blur_2_0001_0_0"]={
		{{0.166666667, 0, 0.66666667, 1, }, {0, 2, }, {{0, }, {35, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {2, 6, }, {{35, }, {25, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {6, 10, }, {{25, }, {16, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {10, 14, }, {{16, }, {10, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {14, 18, }, {{10, }, {9, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {18, 22, }, {{9, }, {4, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {22, 26, }, {{4, }, {0, }, }, }, 
	}, 
	["ADBE_Motion_Blur_0002_0_1"]={
		{{0.166666667, 0, 0.66666667, 1, }, {0, 2, }, {{0, }, {200, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {2, 6, }, {{200, }, {60, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {6, 10, }, {{60, }, {27, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {10, 14, }, {{27, }, {24, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {14, 18, }, {{24, }, {14.1, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {18, 22, }, {{14.1, }, {13, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {22, 26, }, {{13, }, {0, }, }, }, 
	}, 
	["ADBE_Gaussian_Blur_2_0001_2_2"]={
		{{0.166666667, 0, 0.66666667, 1, }, {0, 2, }, {{0, }, {150, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {2, 6, }, {{150, }, {40, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {6, 10, }, {{40, }, {25, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {10, 14, }, {{25, }, {30, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {14, 18, }, {{30, }, {15, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {18, 22, }, {{15, }, {4, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {22, 26, }, {{4, }, {0, }, }, }, 
	}, 
	["ADBE_Motion_Blur_0002_2_3"]={
		{{0.166666667, 0, 0.66666667, 1, }, {0, 2, }, {{0, }, {200, }, }, }, 
		{{0.33333333, 0.33333333, 0.66666667, 0.66666667, }, {2, 6, }, {{200, }, {200, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {6, 10, }, {{200, }, {240, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {10, 14, }, {{240, }, {121.7, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {14, 18, }, {{121.7, }, {30, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {18, 22, }, {{30, }, {13, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {22, 26, }, {{13, }, {0, }, }, }, 
	}, 
	["ADBE_Gaussian_Blur_2_0001_4_4"]={
		{{0.166666667, 0, 0.66666667, 1, }, {0, 2, }, {{0, }, {150, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {2, 6, }, {{150, }, {40, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {6, 10, }, {{40, }, {25, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {10, 14, }, {{25, }, {47.1, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {14, 18, }, {{47.1, }, {0, }, }, }, 
	}, 
	["ADBE_Motion_Blur_0002_4_5"]={
		{{0.166666667, 0, 0.66666667, 1, }, {0, 2, }, {{0, }, {200, }, }, }, 
		{{0.33333333, 0.33333333, 0.66666667, 0.66666667, }, {2, 6, }, {{200, }, {200, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {6, 10, }, {{200, }, {240, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {10, 14, }, {{240, }, {113.1, }, }, }, 
		{{0.33333333, 0, 0.66666667, 1, }, {14, 18, }, {{113.1, }, {0, }, }, }, 
	}, 
}

AnimScript.__index = AnimScript
function AnimScript.new()
    local self = {}
    self = setmetatable({}, AnimScript)

    self.transform = {}
    self.first = true
    self.duration = 1.0
    self.cur_time = 0.0
    self.progress = 0
    self.auto_play = false
    self.renderer = nil
    self.material = nil
    self.pre_bloom_path = ""
    
    -------------------clone-----------------
    self.cloneEntity = {}
    self.cloneEntityRenderer = {}
    self.cloneEffectLayers = {}
    self.cloneEffectParams = {}
    self.ctrans = {}
    self.cloneMaterial={} -------------------clone-----------------
    self.cloneText = {} --sdf
    self.clone_richText = {} 

    self.util = includeRelativePath("Util")

    return self
end


function AnimScript:initMaterial(comp)
    self.renderer = nil
	if self.text ~= nil then
		self.renderer = comp.entity:getComponent("MeshRenderer")
	end
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if self.effect_material then
        InsMaterials = self.effect_material:instantiate()
    else
        InsMaterials = self.renderer.material
    end
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials
    self.material = self.renderer.material

end

---@param comp Component
function AnimScript:onStart(comp)
    self.attrs = includeRelativePath("AETools"):new(ae_attribute1)
    self.comp = comp
    self.text = comp.entity:getComponent('SDFText')
    self.rich_text = comp.entity:getComponent('Text')
    self.trans = comp.entity:getComponent('Transform')
    self.parentTrans = self.trans.parent
    Amaz.LOGI("dkdkkdkdkd",tostring(self.parentTrans))
    self.textEntity=comp.entity
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
            self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.text:forceTypeSetting() 
    self.first = true
end


-------------------------clone--------------------------------------
function AnimScript:getLayer()
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

function AnimScript:setMatToSDFText(i,text, rendermaterial,clonematerial)
    text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if clonematerial then
        InsMaterials = clonematerial:instantiate()
    end
    materials:pushBack(InsMaterials)

    rendermaterial.materials = materials
    self.cloneMaterial[i] = rendermaterial.material
    return rendermaterial.material
end

function AnimScript:addEffectLayers(i)
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

function AnimScript:addEntity(i)

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
            self.clone_richText[i].letters = self.clone_richText[i].letters
			self.cloneText[i]:setTextWrapper(self.clone_richText[i])
		end
		-- self.cloneText[i].str=self.originText 
		self.cloneText[i].backgroundColor = Amaz.Vector4f(0,0,0,0)
		self.cloneText[i]:forceTypeSetting()
		self.ctrans[i].parent = self.parentTrans
		if self.parentTrans then
			self.parentTrans.children:pushBack(self.ctrans[i])
		end
		self:addEffectLayers(i)
	end
end

function AnimScript:clone(_material)
    local count = #self.cloneEntity
    count = count + 1
    self:addEntity(count)
    self.cloneEntityRenderer[count] = self.cloneEntity[count]:getComponent("MeshRenderer")
    local sdf = self.cloneEntity[count]:getComponent("SDFText")
    local mesh = self.cloneEntity[count]:getComponent("MeshRenderer")
    self:setMatToSDFText(count, sdf,mesh,_material)
    local order_index =1 
    local layer = self:getLayer()
    -- Amaz.LOGI("dkdkkdkdkdk",count)
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


---@param comp Component
---@param deltaTime number
function AnimScript:onUpdate(comp, deltaTime)

    if isEditor then
        if self.auto_play then
            self.cur_time = self.cur_time + deltaTime
        end
        self:seek(self.cur_time)
    else
        self.cur_time = 0
    end
end


function AnimScript:getProgress(animtype,time)
    local progress = 0
    local duration = self.duration
    duration = duration <= 0 and 0.0001 or duration
    if animtype == ANIMATIONTYPE.IN then
        progress = self.util.clamp(0,1,time/duration)
    elseif animtype == ANIMATIONTYPE.OUT then
        progress = self.util.clamp(0,1,1.0 - time/duration)
    elseif animtype == ANIMATIONTYPE.LOOP then
        progress = (time % duration) / duration
    elseif animtype == ANIMATIONTYPE.SUBTITLE then
        progress = self:getSubTitleProgress(time)
    end
    return progress
end


function AnimScript:isvalidchar(char)
    local code = char.utf8code
    if code == ' ' or code == '\r' or code == '\n' then
        return false
    end
    return true
end

function AnimScript:getFontSize()
    local letters = self.rich_text.letters
    local fontsize = 8
    if letters:size() > 0 then
        local letter0 = letters:get(0)
        fontsize = letter0.letterStyle.fontSize
    end
    return fontsize
end

function AnimScript:getTextLineCount()
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

function AnimScript:seek(time)
    if isEditor then
        if self.auto_play then
            self.progress = (time % self.duration) / self.duration
        end
    else
        self.progress = self:getProgress(ANIMATIONTYPE.OUT,time)
    end


    if self.first then
        local text = self.rich_text
        if text then 
            if text.BloomPath then
                self.pre_bloom_path = text.BloomPath
                text.BloomPath = ""
    
            elseif text.bloomPath then
                self.pre_bloom_path = text.bloomPath
                text.bloomPath = ""
            end
        end
        self:initMaterial(self.comp) 
        self.first = false
        if self:getTextLineCount() > 1 then
            self:clone(self.clone_material)
        end
    end
    
    self.typeSettingKind = self.text.typeSettingKind
    local h = Amaz.BuiltinObject:getOutputTextureHeight()
    local w = Amaz.BuiltinObject:getOutputTextureWidth()
    self.text.targetRTExtraSize = Amaz.Vector2f(w * 0.80, h * 0.400)


    -- local str = self.text.str
    for i, value in pairs(self.cloneText) do
        -- self.cloneText[i].str=str
        -- self.cloneText[i]:forceTypeSetting()
        self.cloneText[i].targetRTExtraSize = Amaz.Vector2f(w * 0.80, h * 0.400)

    end

    local expandSize1 = self.text:getRectExpanded()
    local expandSize = {x = expandSize1.x - 0.4*w ,y = expandSize1.y - 0.2*h ,width = expandSize1.width + 0.8*w,height = expandSize1.height+ 0.4*h}

    local linneCharTab = {}
    local count = self.text.chars:size()
    local cloneCharTab = {}
    local linecount = self:getTextLineCount()
    for index = 1, count do
        local char = self.text.chars:get(index-1)
        local cloneChar = nil

        local rowth = char.rowth
        linneCharTab[rowth+1] = linneCharTab[rowth+1] or {}
        if linecount > 1 then
            cloneChar = self.cloneText[1].chars:get(index-1)
            cloneCharTab[rowth+1] = cloneCharTab[rowth+1] or {}
        end
        if self:isvalidchar(char) then
            table.insert(linneCharTab[rowth+1],char)
            if rowth%2 == 1 then
                char.scale = Amaz.Vector3f(char.scale.x, 0.0,0.0)
                if cloneChar then
                    cloneChar.scale = Amaz.Vector3f(char.scale.x, 1.0,1.0)
                end
            else
                if cloneChar then
                    cloneChar.scale = Amaz.Vector3f(char.scale.x, 0.0,0.0)
                end
                char.scale = Amaz.Vector3f(char.scale.x, 1.0,1.0)
            end
            if linecount > 1 then
                table.insert(cloneCharTab[rowth+1],cloneChar)
            end
        end
    end

    local max_line_count = 0
    for index, value in ipairs(linneCharTab) do
        local linecount = #linneCharTab[index]
        max_line_count =  linecount > max_line_count and linecount or max_line_count
    end

    local ptTab = {}
    local cur_index = 1
    if max_line_count > 0 then
        local totalFrame = 7 + (max_line_count-1)*4
        local progress = self.util.remap(0.08,0.95,self.progress)
        local cur_frame = progress*totalFrame
        for index = 1, max_line_count do
            local begin_index = 2 + (index-1)*4
            local end_frame  = 10 + (index-1)*4

            local cur_progress = self.util.remap(begin_index, end_frame, cur_frame)
            local b_scale_pt = self.util.bezier({0.053093827, -0.001375441, 0.425349219,1,})(cur_progress,0, 1, 1)

            local cur_progress1 = self.util.remap(begin_index-1, end_frame-3, cur_frame)
            if cur_progress1 > 0 then
                cur_index = index
            end
            local b_opt_pt = self.util.bezier({0.053093827, 0.002166319, 0.425349219, 1, })(cur_progress1,0, 1, 1)
            local opt = self.util.mix(0,1.0,b_opt_pt)
            table.insert(ptTab,opt)

            for key, value in pairs(linneCharTab) do
                local lineInfo = linneCharTab[key]
                local cloneInfo = cloneCharTab[key]
                local linecount = #lineInfo


                if linecount >= index then
                    local begin_scale = 3.1 - 1.2*(index)/linecount
                    local scale = self.util.mix(begin_scale,1.0,b_scale_pt)

                    local char = lineInfo[index]
                    if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then
		                char.scale = Amaz.Vector3f(char.scale.x, scale, char.scale.z)
                    else
		                char.scale = Amaz.Vector3f(scale, char.scale.y, char.scale.z)
                    end
                    char.color = Amaz.Vector4f(char.color.x, char.color.y, char.color.z,opt)
                    if cloneInfo then
                        local char = cloneInfo[index]
                        if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then
                            char.scale = Amaz.Vector3f(char.scale.x, scale, char.scale.z)
                        else
                            char.scale = Amaz.Vector3f(scale, char.scale.y, char.scale.z)
                        end
                        char.color = Amaz.Vector4f(char.color.x, char.color.y, char.color.z,opt)
                    end

                end
            end
        end
    end


    local radius = 16
    self.material:enableMacro("SAMPLETIIMES1", math.floor(radius ))
    if  self.cloneMaterial[1] then
        self.cloneMaterial[1]:enableMacro("SAMPLETIIMES1", math.floor(radius ))
    end


    local step = 10
    local b0 = self.attrs:GetVal("ADBE_Gaussian_Blur_2_0001_0_0", self.progress)[1]/step
    local b1 = self.attrs:GetVal("ADBE_Gaussian_Blur_2_0001_2_2", self.progress)[1]/step
    local b2 = self.attrs:GetVal("ADBE_Gaussian_Blur_2_0001_4_4", self.progress)[1]/step

    local d0 = self.attrs:GetVal("ADBE_Motion_Blur_0002_0_1", self.progress)[1]
    local d1 = self.attrs:GetVal("ADBE_Motion_Blur_0002_2_3", self.progress)[1]
    local d2 = self.attrs:GetVal("ADBE_Motion_Blur_0002_4_5", self.progress)[1]

    local scale = self.parentTrans.localScale.x
    local fontsize = self:getFontSize()
    local fix_num = fontsize/22

    local multi_num1 = scale*fix_num
    local multi_num = 10.0
    if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then 
        multi_num1 = multi_num1*expandSize.height/expandSize.width
        multi_num = multi_num*expandSize.height/expandSize.width
    end
    b0 = 5*multi_num1
    b1 = 10*multi_num1
    b2 = 12*multi_num1

    d0 = 8*multi_num
    d1 = 20*multi_num
    d2 = 35*multi_num


    b0 = b0/step
    b1 = b1/step
    b2 = b2/step

    self.material:enableMacro("SAMPLETIIMES2", math.floor(d2))
    self.material:enableMacro("SAMPLETIIMES3", math.floor(d1))
    self.material:enableMacro("SAMPLETIIMES4", math.floor(d0))

    self.material:setFloat("gauss_stron",b2)
    self.material:setFloat("gauss_stron1",b1)
    self.material:setFloat("gauss_stron2",b0)

    local angle = self.parentTrans.localEulerAngle.z
    if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then
        angle = angle + 90
    end
    self.material:setFloat("u_Angle",angle/180)
    self.material:setFloat("angle",angle)

    local material = self.cloneMaterial[1]
    if  material then
        material:enableMacro("SAMPLETIIMES2", math.floor(d2))
        material:enableMacro("SAMPLETIIMES3", math.floor(d1))
        material:enableMacro("SAMPLETIIMES4", math.floor(d0))
        material:setFloat("gauss_stron",b2)
        material:setFloat("gauss_stron1",b1)
        material:setFloat("gauss_stron2",b0)
        material:setFloat("u_Angle",angle/180)
        material:setFloat("angle",angle)
    end

    local lineCount = #linneCharTab
    local total_width = 0
    local char_count = 0
    for index, value in pairs(linneCharTab) do
        local linenum = #linneCharTab[index]
        if linenum > 0 then
            local lineInfo = linneCharTab[index]
            local cloneInfo = cloneCharTab[index]
            local left_down_point = nil
            local right_up_point = nil
            char_count = char_count + linenum
            for i = 1, linenum do
                local char = lineInfo[i]
                local ori_pos = char.initialPosition
                local width_space = char.width * 0.5
                total_width = total_width + width_space*2.0
                local height_space = char.height * 0.5
                if left_down_point == nil then
                    left_down_point = Amaz.Vector2f(
                        ori_pos.x-width_space, 
                        ori_pos.y-height_space
                    )
                else
                    local curx = ori_pos.x-width_space
                    local cury = ori_pos.y-height_space
                    left_down_point = Amaz.Vector2f(
                        left_down_point.x < curx and left_down_point.x or curx,
                        left_down_point.y < cury and left_down_point.y or cury
                    )
                end

                if right_up_point == nil then
                    right_up_point = Amaz.Vector2f(
                        ori_pos.x+width_space, 
                        ori_pos.y+height_space
                    )
                else
                    local curx = ori_pos.x+width_space
                    local cury = ori_pos.y+height_space
                    right_up_point = Amaz.Vector2f(
                        right_up_point.x > curx and right_up_point.x or curx,
                        right_up_point.y > cury and right_up_point.y or cury
                    )
                end

            end


            char_count = char_count >= 1 and char_count or 1

            local avg_width = total_width/char_count
            if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then 
                avg_width = avg_width/expandSize.height*0.8 
                self.material:setFloat("s_width",8*expandSize.width/expandSize.height)
                if material then
                    material:setFloat("s_width",8*expandSize.width/expandSize.height)
                end
            else
                avg_width = avg_width/expandSize.width 
            end

            self.material:setFloat("width",avg_width*0.5)
            if material then
                material:setFloat("width",avg_width*0.5)
            end


            local ldp = left_down_point
            local rup = right_up_point

            local x1 = (ldp.x - expandSize.x)/expandSize.width-1.0*avg_width
            local x2 = (rup.x - expandSize.x)/expandSize.width+1.0*avg_width

            -- if max_line_count/linenum == 1 then
            --     x2 = (rup.x - expandSize.x)/expandSize.width+2.0*avg_width
            -- end
            local y1 = (ldp.y - expandSize.y)/expandSize.height
            local y2 = (rup.y - expandSize.y)/expandSize.height

            if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then 
                self.material:setFloat("typeSetting",1.0)
                if material then
                    material:setFloat("typeSetting",1.0)
                end
                y1 = (ldp.x - expandSize.x)/expandSize.width
                y2 = (rup.x - expandSize.x)/expandSize.width
        
                x1 = (rup.y - expandSize.y)/expandSize.height+1.0*avg_width
                x2 = (ldp.y - expandSize.y)/expandSize.height
            else
                self.material:setFloat("typeSetting",0.0)
                if material then
                    material:setFloat("typeSetting",0.0)
                end
            end

            local progress = self.util.remap(0.0,0.935,self.progress*max_line_count/linenum)

            local s_x= self.util.mix(x1,x2,progress)
            local low_blur = (x2- avg_width*2-x1)/(x2-x1)
            if self.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then 
                low_blur = (x1- avg_width*2.5-x2)/(x1-x2)
            end

            low_blur = low_blur < 0.5 and 0.5 or low_blur
            local maskalpha = 1.0-self.util.remap(low_blur,1.0,self.progress*max_line_count/linenum)

            local low_blur = (avg_width*4.)/(x2-x1)
            low_blur = low_blur > 0.5 and 0.5 or low_blur
            local line_alpha = self.util.remap(0,low_blur,self.progress*max_line_count/linenum)

            for i = 1, linenum do
                local char = lineInfo[i]
                char.color = Amaz.Vector4f(char.color.x, char.color.y, char.color.z,char.color.w*line_alpha)
                if cloneInfo then
                    local char = cloneInfo[i]
                    char.color = Amaz.Vector4f(char.color.x, char.color.y, char.color.z,char.color.w*line_alpha)
                end
            end

            if index%2 == 1 then
                if lineCount%2 == 0 then
                    self.material:setFloat("lineCount",math.floor(lineCount/2))
                elseif lineCount%2 == 1 then
                    self.material:setFloat("lineCount",math.ceil(lineCount/2))
                end
                local count = (index+1)/2
                self.material:setVec4("mask"..count,Amaz.Vector4f(s_x,y1, y2,maskalpha))
            else
                local count = index/2
                if material then
                    material:setFloat("lineCount",math.floor(lineCount/2))
                    material:setVec4("mask"..count,Amaz.Vector4f(s_x,y1, y2,maskalpha))
                end
            end
        end
    end

    local text = self.rich_text
    for key, richText in pairs(self.clone_richText) do
        if text.BloomPath then
            richText.BloomPath = ""
        elseif text.bloomPath then
            richText.bloomPath = ""
        end
    end
    


------------------------------------------------------------
end


function AnimScript:setDuration(duration)
   self.duration = duration
end


function AnimScript:resetData( ... )
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

    self.text.renderToRT = false 
    self.text.chars = chars
    self.text.targetRTExtraSize = Amaz.Vector2f(0.0, 0.0) 
    for i, value in pairs(self.cloneEntity) do
        self.textEntity.scene:removeEntity(self.cloneEntity[i])
        if self.parentTrans.children:size() > 1 and self.cloneEntity[i] then
            self.parentTrans.children:erase(self.cloneEntity[i])
        end
        self.cloneEntity[i] = nil
    end
    self.cloneEntity = {}
    local text = self.rich_text
    if text then
        if text.BloomPath then
            text.BloomPath = self.pre_bloom_path
        elseif text.bloomPath then
            text.bloomPath = self.pre_bloom_path
        end
    end
end

function AnimScript:onLeave()
    self:resetData()
end

function AnimScript:clear()
    self:resetData()
end

function AnimScript:onEnter()
    self.first = true
end


exports.AnimScript = AnimScript
return exports
