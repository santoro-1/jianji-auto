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
	["ADBE_Scale_0_1"]={
		{{0.166666667,0.166666667,0.166666667, 0.166666667,0.166666667,0.166666667, 0.833333333,0.833333333,0.833333333, 0.833333333,0.833333333,0.833333333, }, {0, 4, }, {{18, 18, 100, }, {60, 60, 100, }, }, }, 
		{{0.166666667,0.166666667,0.166666667, 0.166666667,0.166666667,0.166666667, 0.833333333,0.833333333,0.833333333, 0.833333333,0.833333333,0.833333333, }, {4, 25, }, {{60, 60, 100, }, {65, 65, 100, }, }, }, 
	}, 
	["ADBE_Opacity_0_2"]={
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {0, 4, }, {{0, }, {100, }, }, }, 
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {4, 19, }, {{100, }, {100, }, }, }, 
		{{0.166666667, 0.166666667, 0.833333333, 0.833333333, }, {19, 25, }, {{100, }, {0, }, }, }, 
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
    self.cloneMaterial={} 
    self.cloneText = {} 
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
    self.attrs = includeRelativePath("AETools"):new(ae_attribute)
    self.comp = comp
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
        -- local parent_idx=layer*order_index
        self.cloneEntityRenderer[count].autoSortingOrder=false
        self.cloneEntityRenderer[count].sortingOrder=self.renderer.sortingOrder+1
        -- self.cloneEntityRenderer[count].sortingOrder=parent_idx+count
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
    if code == '\r' or code == '\n' then
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



function AnimScript:getAvgWidth()
    local total_width = 0
    local count = self.text.chars:size()
    for index = 1, count do
        local char = self.text.chars:get(index-1)
        total_width = total_width + char.width
    end 
    if count > 0 then
        local avg_width = total_width/count
        return avg_width
    else
        return 0
    end
end



function AnimScript:getPos(thetha,center,a,b)
    local x = a*math.sin(thetha) + center.x
    local y = b*math.cos(thetha) + center.y
    return x,y
end

function AnimScript:getPos1(thetha,center,a,b)
    local x = a*math.cos(thetha) + center.x
    local y = b*math.sin(thetha) + center.y
    return x,y
end

function AnimScript:getPosByalightType(lineInfo,center,radius,thetha,maxLineNum)
    local PI = 3.1415926
    local lineNum = #lineInfo
    local orgCharInfo = {}
    for index, char in ipairs(lineInfo) do
        -- if maxLineNum == lineNum then
        --     local t1 = self.util.mix(-thetha,thetha,(index-1)/(lineNum-1))
        --     if self.typeSettingKind == 1 then
        --         t1 = t1 + PI/2
        --     end
        --     local x,y = self:getPos(t1,center,radius,radius)
        --     local rotate = Amaz.Vector3f(0,0,
        --     -180*t1/PI
        --     )
        --     if self.typeSettingKind == 1 then
        --          rotate = Amaz.Vector3f(0,0,
        --         -180*t1/PI + 90
        --         )
        --     end

        --     local position = Amaz.Vector3f(x,y, char.initialPosition.z)
        --     local item = {rotate = rotate,position = position}
        --     table.insert(orgCharInfo,item)
        -- else
            if  self.typeSettingKind == 0 then -- HORIZONTAL
                if self.textAlign == 0 then -- left
                    local t1 = -thetha - (self.maxtheTa-thetha)
                    if maxLineNum >1 then
                        t1 = 2*thetha*(index-1)/(maxLineNum-1) -thetha - (self.maxtheTa-thetha)
                    end
                    local x,y = self:getPos(t1,center,radius,radius)
                    local rotate = Amaz.Vector3f(0,0,
                    -180*t1/PI
                    )
                    local position = Amaz.Vector3f(x,y, char.initialPosition.z)
                    local item = {rotate = rotate,position = position}
                    table.insert(orgCharInfo,item)
                elseif self.textAlign == 2 then -- right
                    -- local endThetha = thetha - 2*thetha*lineNum/maxLineNum
                    -- local t1 = self.util.mix(endThetha,thetha,(index-1)/(lineNum-1))
                    local t1 = thetha + (self.maxtheTa-thetha)
                    if maxLineNum > 1 then
                        t1 = thetha - 2*thetha*(lineNum-1)/(maxLineNum-1)*(lineNum - index)/(lineNum-1)+ (self.maxtheTa-thetha)
                    end


                    local x,y = self:getPos(t1,center,radius,radius)
                    local rotate = Amaz.Vector3f(0,0,
                    -180*t1/PI
                    )
                    local position = Amaz.Vector3f(x,y, char.initialPosition.z)
                    local item = {rotate = rotate,position = position}
                    table.insert(orgCharInfo,item)
                else
                    local endThetha = thetha
                    local t1 = thetha
                    if maxLineNum > 1 then
                        endThetha = (thetha - thetha*(maxLineNum- lineNum)/(maxLineNum-1))
                        t1 = self.util.mix(-endThetha,endThetha,(index-1)/(lineNum-1))
                    end

                    local x,y = self:getPos(t1,center,radius,radius)
                    local rotate = Amaz.Vector3f(0,0,
                    -180*t1/PI
                    )
                    local position = Amaz.Vector3f(x,y, char.initialPosition.z)
                    local item = {rotate = rotate,position = position}
                    table.insert(orgCharInfo,item)
                end
            else --vertical
                if self.textAlign == 3 then -- up
                    local t1 =  -thetha + PI/2- (self.maxtheTa-thetha)
                    if maxLineNum > 1 then
                        t1 = 2*thetha*(index-1)/(maxLineNum-1) -thetha + PI/2- (self.maxtheTa-thetha)
                    end

                    local x,y = self:getPos(t1,center,radius,radius)
                    local rot =  -180*t1/PI 
                    
                    local rotate = Amaz.Vector3f(0,0,
                    rot
                    )
                    if self.typeSettingKind == 1 then
                        rotate = Amaz.Vector3f(0,0,
                       -180*t1/PI + 90
                       )
                   end
                    -- Amaz.LOGI("eiieieiei",index.."eke"..t1)
                    local position = Amaz.Vector3f(x,y, char.initialPosition.z)
                    local item = {rotate = rotate,position = position}
                    table.insert(orgCharInfo,item)

                elseif self.textAlign == 4 then -- down
                    local t1 =  thetha + PI/2+ (self.maxtheTa-thetha)
                    if maxLineNum > 1 then
                        t1 = thetha - 2*thetha*(lineNum-1)/(maxLineNum-1)*(lineNum - index)/(lineNum-1) + PI/2+ (self.maxtheTa-thetha)
                    end

                    local x,y = self:getPos(t1,center,radius,radius)
                    local rotate = Amaz.Vector3f(0,0,
                    -180*t1/PI
                    )
                    if self.typeSettingKind == 1 then
                        rotate = Amaz.Vector3f(0,0,
                       -180*t1/PI + 90
                       )
                   end
                    local position = Amaz.Vector3f(x,y, char.initialPosition.z)
                    local item = {rotate = rotate,position = position}
                    table.insert(orgCharInfo,item)
                else

                    local t1 =  thetha 
                    local endThetha = thetha
                    if maxLineNum > 1 then
                        endThetha = (thetha - thetha*(maxLineNum- lineNum)/(maxLineNum-1))
                        t1 = self.util.mix(-endThetha,endThetha,(index-1)/(lineNum-1))+ PI/2
                    end

                    local endThetha = (thetha - thetha*(maxLineNum- lineNum)/(maxLineNum-1))
                    local t1 = self.util.mix(-endThetha,endThetha,(index-1)/(lineNum-1))+ PI/2
                    local x,y = self:getPos(t1,center,radius,radius)
                    local rotate = Amaz.Vector3f(0,0,
                    -180*t1/PI
                    )
                    if self.typeSettingKind == 1 then
                        rotate = Amaz.Vector3f(0,0,
                       -180*t1/PI + 90
                       )
                   end
                    local position = Amaz.Vector3f(x,y, char.initialPosition.z)
                    local item = {rotate = rotate,position = position}
                    table.insert(orgCharInfo,item)
                end
            end
        end
    -- end
    return orgCharInfo
end


function AnimScript:seek(time)
    if isEditor then
        if self.auto_play then
            self.progress = (time % self.duration) / self.duration
        end
    else
        self.progress = self:getProgress(ANIMATIONTYPE.LOOP,time)
    end


    if self.first then
        -- self:initMaterial(self.comp) 
        self.first = false
    end
    
    self.typeSettingKind = self.text.typeSettingKind
    self.textAlign = self.text.textAlign
    local h = Amaz.BuiltinObject:getOutputTextureHeight()
    local w = Amaz.BuiltinObject:getOutputTextureWidth()
    self.text.targetRTExtraSize = Amaz.Vector2f(w * 0.40, h * 0.400)

    local linneCharTab = {}
    local count = self.text.chars:size()
    self.count = count
    local cloneCharTab = {}
    local linecount = self:getTextLineCount()

    for index = 1, count do
        local char = self.text.chars:get(index-1)
        local rowth = char.rowth
        linneCharTab[rowth+1] = linneCharTab[rowth+1] or {}
        if linecount > 1 then
            cloneCharTab[rowth+1] = cloneCharTab[rowth+1] or {}
        end
        if self:isvalidchar(char) then
            table.insert(linneCharTab[rowth+1],char)
        end
    end
    local width = self.text.rect.width
    local height = self.text.rect.height
    local PI = 3.1415926

    local avg_h = height/linecount
    if self.typeSettingKind == 1 then
        avg_h = width/linecount
    end




    local getLineAvgH = function(lineInfo)
        local avg_h = 0
        local numCount = 0
        for index, char in ipairs(lineInfo) do
            if char.utf8code ~= " " then
                if self.typeSettingKind == 1 then
                    avg_h = avg_h + char.initialPosition.x
                else
                    avg_h = avg_h + char.initialPosition.y

                end
                numCount = numCount + 1
            end

        end
        if numCount >= 1 then
            return avg_h/numCount
        else
            return 0
        end
    end
    local alpha = self.attrs:GetVal("ADBE_Opacity_0_2", self.progress)[1]/100
    linecount = linecount < 2 and 2 or linecount
    local radius_p = (width*0.5 + avg_h*1.5*(linecount - 1) + height*1.2)/(width*0.5 + avg_h*1.2*(linecount - 1))
    if self.typeSettingKind == 1 then
        radius_p = (height*0.5 + avg_h*1.5*(linecount - 1) + width*1.2)/(height*0.5 + avg_h*1.2*(linecount - 1))
    end
    local fscale = 1
    if self.progress< 4/25 then
        local pt = self.progress
        pt = self.util.remap(0,4/25,self.progress)
        fscale = self.util.bezier({0.166667, 0.166667, 0.833333, 0.833333, })(pt,0,1,1)
        fscale = self.util.mix(1,radius_p*0.9,fscale)
    else
        local pt = self.progress
        pt = self.util.remap(4/25,1,self.progress)
        fscale = self.util.bezier({0.166667, 0.166667, 0.833333, 0.833333, })(pt,0,1,1)
        fscale = self.util.mix(radius_p*0.9,radius_p,fscale)
    end

    local f_move = 0
    if self.progress< 4/23 then
        local pt = self.progress
        pt = self.util.remap(0,4/25,self.progress)
        f_move = self.util.bezier({0.166667, 0.166667, 0.833333, 0.833333, })(pt,0,1,1)
        f_move = self.util.mix(0,0.5,f_move)
    else
        local pt = self.progress
        pt = self.util.remap(4/25,1,self.progress)
        f_move = self.util.bezier({0.166667, 0.166667, 0.833333, 0.833333, })(pt,0,1,1)
        f_move = self.util.mix(0.5,1.0,f_move)
    end
    local maxCount = 1
    local maxradius = 10
    local radius_p = 0.75

    local y0 = -width*radius_p*1.1
    local center = {x = 0,y = y0 }
    if self.typeSettingKind == 1 then
        local x0 = -height*radius_p*1.1
        center = {x = x0,y = 0 }
    end
    for index, lineInfo in ipairs(linneCharTab) do
        local curCount = #lineInfo
        local h_slider = 1.2
        local radius = width*radius_p + avg_h*h_slider*(linecount - index)
        local radius1 = width*radius_p + avg_h*h_slider*(linecount - index)*fscale

        local extrasize = avg_h*(1.5+2*self.util.remap(1,4,linecount)+4*self.util.remap(5,30,maxCount))
        if self.typeSettingKind == 1 then

            radius = height*radius_p + avg_h*h_slider*(linecount - index)
            radius1 = height*radius_p + avg_h*h_slider*(linecount - index)*fscale
            extrasize = avg_h*(1.5+2*self.util.remap(1,4,linecount)+4*self.util.remap(5,30,maxCount))
        end
        if maxCount < curCount then
            maxCount = curCount
            maxradius = radius
        end
    end

    for index, lineInfo in ipairs(linneCharTab) do
        local h_slider = 1.2
        local radius = width*radius_p + avg_h*h_slider*(linecount - index)
        local radius1 = width*radius_p + avg_h*h_slider*(linecount - index)*fscale

        local extrasize = avg_h*(1.5+2*self.util.remap(1,4,linecount)+4*self.util.remap(5,30,maxCount))
        if self.typeSettingKind == 1 then

            radius = height*radius_p + avg_h*h_slider*(linecount - index)
            radius1 = height*radius_p + avg_h*h_slider*(linecount - index)*fscale
            extrasize = avg_h*(1.5+2*self.util.remap(1,4,linecount)+4*self.util.remap(5,30,maxCount))
        end
        local thetha = (0.12+0.2*self.util.remap(2,20,maxCount))*PI*maxradius/radius
        self.maxtheTa = self.maxtheTa or thetha
        self.maxtheTa = self.maxtheTa < thetha and thetha or self.maxtheTa
    end


    local startPosInfo = {}
    for index, lineInfo in ipairs(linneCharTab) do

        local h_slider = 1.2
        local radius = width*radius_p + avg_h*h_slider*(linecount - index)
        local radius1 = width*radius_p + avg_h*h_slider*(linecount - index)*fscale
        local extrasize = avg_h*(1.5+2*self.util.remap(1,4,linecount)+4*self.util.remap(5,30,maxCount))
        if self.typeSettingKind == 1 then
            radius = height*radius_p + avg_h*h_slider*(linecount - index)
            radius1 = height*radius_p + avg_h*h_slider*(linecount - index)*fscale
            extrasize = avg_h*(1.5+2*self.util.remap(1,4,linecount)+4*self.util.remap(5,30,maxCount))
        end
        
        -- local thetha = (0.16+0.17*self.util.remap(2,20,#lineInfo))*PI

        -- local curCount = #lineInfo
        -- local extraTheta = 0.2*self.util.remap(0,5,index-1)
        local thetha = (0.12+0.2*self.util.remap(2,20,maxCount))*PI*maxradius/radius

        local initInfo = self:getPosByalightType(lineInfo,center,radius,thetha,maxCount)
        local endInfo = self:getPosByalightType(lineInfo,center,radius1 + extrasize,thetha,maxCount)
        
        -- local fixscale = 
        -- local radian_scale = max_line_scale*math.sqrt(radius/max_line_radius)
        for i, value in ipairs(lineInfo) do
            local start_info = initInfo[i]
            local end_info = endInfo[i]
            local char = value
            local startpos = start_info.position
            table.insert(startPosInfo,startpos)
            local endpos = end_info.position
            local curPosx = self.util.mix(startpos.x,endpos.x,f_move)
            local curPosy = self.util.mix(startpos.y,endpos.y,f_move)
            local curPosz = self.util.mix(startpos.z,endpos.z,f_move)
            char.position = Amaz.Vector3f(curPosx,curPosy,curPosz)
            char.rotate = start_info.rotate
            char.color = Amaz.Vector4f(char.color.x,char.color.y,char.color.z,alpha)
            char.scale = Amaz.Vector3f(fscale, fscale, 1)
        end
        -- local lineNum = #lineInfo
        -- local avgy = getLineAvgH(lineInfo)
        -- local curNum = #lineInfo


    end
    local minx = nil
    local maxx = nil
    local miny = nil
    local maxy = nil
    for index, posInfo in ipairs(startPosInfo) do
        minx = minx or posInfo.x
        minx = minx< posInfo.x and minx or posInfo.x
        maxx = maxx or posInfo.x
        maxx = maxx> posInfo.x and maxx or posInfo.x
        miny = miny or posInfo.y
        miny = miny< posInfo.y and miny or posInfo.y
        maxy = maxy or posInfo.y
        maxy = maxy> posInfo.y and maxy or posInfo.y
    end

    for index, lineInfo in ipairs(linneCharTab) do
        for i, value in ipairs(lineInfo) do
            local char = value
            local pos = char.position
            if self.typeSettingKind == 0 then
                char.position = Amaz.Vector3f(pos.x,pos.y-(miny+maxy)/2 - avg_h,pos.z)
            else
                char.position = Amaz.Vector3f(pos.x-(minx+maxx)/2- avg_h,pos.y,pos.z)
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


function AnimScript:ellipse(center,a,b)
    -- local x = a*sin
end

function AnimScript:line(k,a,b)
    return k
end

function AnimScript:cross(k,a,b,center,a0,b0)
    --y = k(x-a) + b  
    --x = (y -b)/k + a (x-center.x)*(x-center.x)/(a0*a0) + (y-center.y)*(y-center.y)/(b0*b0) = 1

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
