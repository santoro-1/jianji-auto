local exports = exports or {}
local TextAnim = TextAnim or {}
---@class TextAnim:ScriptComponent
---@field autoPlay boolean
---@field isRenderToRT boolean
---@field duration number
---@field progress number [UI(Range={0, 1}, Slider)]
TextAnim.__index = TextAnim

function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.duration = 3.0
    self.progress = 0.0
    self.curTime = 0.0
    self.autoPlay = false
    self.isRenderToRT = true
    self.first = true
    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end

function TextAnim:constructor()
    self.name = "scriptComp"
end
local remap = function(smin, smax, dmin, dmax, value)
    return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end
local remap01 = function(s, t, x)
    return (t - s) * x + s
end
local clamp = function(min, max, value)
    return math.min(math.max(value, min), max)
end
local scaleInFunc = function(x)
    return math.pow(x, 0.5)
end
local scaleOutFunc = function(x)
    return math.pow(x, 2.0)
end

function TextAnim:onStart(comp)
    self.text = comp.entity:getComponent("SDFText")
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
            self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end 
    self.renderer = nil
    if self.text ~= nil then
        self.renderer = comp.entity:getComponent("MeshRenderer")
    else
        self.renderer = comp.entity:getComponent("Sprite2DRenderer")
    end

    self.trans = comp.entity:getComponent("Transform")
    

    self.text:forceTypeSetting()
    self.charsCount = self.text.chars:size()
    local count = 0
    for i = 0, self.charsCount - 1 do
        if self.text.chars:get(i).utf8code ~= "\n" then
            count = count + 1
        end
    end
    self.charsCount = count
    self.charAnimForward = 0.3  --zi yu zi zhi jian de jian ge, fan wei shi [0, 1]
    self.charAnimDuration = 1.0 / (self.charsCount - self.charAnimForward * (self.charsCount - 1.0))
    self.charAnimForward = self.charAnimForward * self.charAnimDuration
    self.CharsProp = {
        ['scale'] = {
            {0.0, 0.7, 0.0, 1.1, func = scaleInFunc},
            {0.7, 1.0, 1.1, 1.0, func = scaleOutFunc}
        }
    } 
    self:seek(0)

    self.first = true
end

function TextAnim:onUpdate(comp, deltaTime)
    if Amaz.Macros and Amaz.Macros.EditorSDK then
        self.text.renderToRT = self.isRenderToRT
        self.curTime = self.curTime + deltaTime
        self:seek(self.curTime)
    end
end

local getValue = function(propList, progress)
    local p = propList.func(remap(propList[1], propList[2], 0, 1,progress))
    return remap(0, 1, propList[3], propList[4], p)
end
local getCurTimeInWhichRange = function(propList, progress)
    for j = #propList, 1, -1 do
        if progress >= propList[j][1] then
            return j
        end
    end
end

function TextAnim:textZoomIn(progress)
    local chars = self.text.chars
    local charsCount = self.text.chars:size()
    local count = 0
    for i = 0, charsCount - 1 do
        if chars:get(i).utf8code ~= "\n" then
            count = count + 1
        end
    end
    if self.charsCount ~= count then
        self.charsCount = count
        self.charAnimForward = 0.3  --zi yu zi zhi jian de jian ge, fan wei shi [0, 1]
        self.charAnimDuration = 1.0 / (count - self.charAnimForward * (count - 1.0))
        self.charAnimForward = self.charAnimForward * self.charAnimDuration
    end
    local index = 0
    for i = 1, charsCount do
        local char = chars:get(i - 1)

        if char.utf8code ~= "\n" then
            local t = clamp(0, self.charAnimDuration, progress - (index) * self.charAnimDuration + (index) * self.charAnimForward)
            local charProgress = remap(0, self.charAnimDuration, 0.0, 1.0, t)

            local scaleList = self.CharsProp["scale"]
            local k = getCurTimeInWhichRange(scaleList, charProgress)
            local scale = getValue(scaleList[k], charProgress)
            char.scale = Amaz.Vector3f(scale, scale, 1.0)
            index = index + 1

        end
    end
    self.text.chars = chars

end

function TextAnim:setMatToSDFText()
    local materials = Amaz.Vector()
    local InsMaterials = nil
    if self.sharedMaterial then
        InsMaterials = self.sharedMaterial:instantiate()
    else
        InsMaterials = self.renderer.material
    end
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials

    self.material = self.renderer.material
end

function TextAnim:seek(time)

    local w = Amaz.BuiltinObject:getInputTextureWidth()
    local h = Amaz.BuiltinObject:getInputTextureHeight()

    if Amaz.Macros and Amaz.Macros.EditorSDK then
        if self.autoPlay then
            self.progress = time % self.duration / self.duration
        end
    else
        self.progress = clamp(0.0, 1.0, time / self.duration)
        if self.first == true then
            self.text.renderToRT = true
            if self.text.renderToRT == true then
                self:setMatToSDFText()
            end
            self.first = false
        end
    end

    local k = h / 720;

    self.text:forceTypeSetting()
    self.material:setFloat("u_Flag", self.text.typeSettingKind)
    self:textZoomIn(self.progress)
    self.trans.localPosition = Amaz.Vector3f(0, -0.02 / k, 0)
end

function TextAnim:onEnter()
    self.first = true
    
end
function TextAnim:resetData( ... )
    if self.text ~= nil then
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
        self.text.chars = chars
    end

    self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
    self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
    self.trans.localScale = Amaz.Vector3f(1, 1, 1)
end

function TextAnim:setDuration(duration)
   self.duration = duration
end
function TextAnim:onLeave()
    self:resetData()
    self.text.renderToRT = false
    self.first = true
end
function TextAnim:clear()
    self:resetData()
    self.text.renderToRT = false
end

exports.TextAnim = TextAnim
return exports
