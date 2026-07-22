local exports = exports or {}
local TextAnim1 = TextAnim1 or {}
---@class TextAnim1:ScriptComponent
---@field effectMaterial Material
---@field curTime number
TextAnim1.__index = TextAnim1

function TextAnim1.new(construct, ...)
    local self = setmetatable({}, TextAnim1)
    self.effectMaterial = nil
    self.curTime = 0
    if construct and TextAnim1.constructor then TextAnim1.constructor(self, ...) end
    return self
end

function TextAnim1:constructor()
    self.name = "scriptComp"
end

local function getRootDir()
    local rootDir = nil
    if rootDir == nil then
        local str = debug.getinfo(2, "S").source
        rootDir = str:match("@?(.*/)")
    end
    -- Amaz.LOGI("lrc getRootDir 3", tostring(rootDir))
    return rootDir
end


local updataGrad = function(color, scale)
    local grad = Amaz.GradientChange()
    local color1 = Amaz.ColorChange()
    color1.color = color
    grad.color1 = color1
    grad.scale = scale
    return grad
end


local addEffectLayer = function(effectTextParam, material)
    local newEffectLayer = Amaz.EffectLayer()
    newEffectLayer.mat = material
    local grad = Amaz.GradientChange()
    local color1 = Amaz.ColorChange()
    color1.change = false
    color1.percent = 0.0
    color1.color = Amaz.Color(1.0, 0.0, 1.0, 1.0)
    color1.hsbOffset = Amaz.Vector3f(0.0, 0.0, 0.0)
    color1.alphaOffset = 0
    grad.color1 = color1
    grad.color2 = nil
    grad.color3 = nil
    grad.scale = 0.5
    grad.angle = 0.0
    grad.gradient_type = 0
    grad.percent1_2 = 0.0
    grad.percent2_3 = 0.0
    grad.linear = true
    newEffectLayer.grad = grad

    -- local outline1Grad = Amaz.GradientChange()
    -- color1 = Amaz.ColorChange()
    -- color1.color = Amaz.Color(0.22, 1.0, 0.0, 1.0)
    -- outline1Grad.color1 = color1
    -- outline1Grad.scale = 0.01
    -- newEffectLayer.outline1Grad = outline1Grad
    effectTextParam.effectLayers:pushBack(newEffectLayer)
end

local addEffectText = function(textComponent, material)
    if textComponent.effectTextParam == nil then
        textComponent.effectTextParam = Amaz.EffectTextParam()
        textComponent.effectTextParam.version = 0
        textComponent.effectTextParam.textColor = Amaz.Color(1.0, 1.0, 1.0, 1.0)
        textComponent.effectTextParam.outlineMaxWidth = 0.2
        textComponent.effectTextParam.randomGridSize = Amaz.Vector2f(1.0, 1.0)
        textComponent.effectTextParam.effectLayers = Amaz.Vector()
        addEffectLayer(textComponent.effectTextParam, material)
    else
        -- addEffectLayer(textComponent.effectTextParam, material)
    end

end

function TextAnim1:onStart(comp)
    self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
            self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end

    self.rootDir = getRootDir()

    -- Amaz.LOGI("lrc", tostring(self.rootDir))
    self.effectText_prefab = Amaz.PrefabManager.loadPrefab(self.rootDir, self.rootDir .. "prefabs/kkk.prefab")
    local e = self.effectText_prefab:instantiateToEntity(comp.entity.scene, comp.entity)

    -- local effectTextEntity = self.effectText_prefab.entities:get(0)
    -- local effectTextSDF = effectTextEntity:getComponent("SDFText")
    -- self.text.effectTextParam = effectTextSDF.effectTextParam
    -- self.text.effectTextParam.effectLayers:get(0).mat = self.effectMaterial
    -- addEffectText(self.text, self.effectMaterial)
    -- addEffectLayer(self.text.effectTextParam)
    -- self.effectLayer0 = self.text.effectTextParam.effectLayers:get(0)
end

function TextAnim1:onUpdate(comp, deltaTime)
    -- self.effectLayer0.outline1Grad.color1.color = Amaz.Color(color.x, color.y, color.z, color.w)
    if Amaz.Macros and Amaz.Macros.EditorSDK then
        self:seek(self.curTime)
        self.curTime = self.curTime + deltaTime
    else
    end


end

function TextAnim1:seek(time)
    local color = self.text.textColor
    -- self.effectLayer0.mat:setFloat("t", time)
    -- self.effectLayer0.grad = updataGrad(Amaz.Color(0.0, 0.0, 0.0, 0.0), 0.0)
    -- self.effectLayer0.outline1Grad = updataGrad(Amaz.Color(color.x, color.y, color.z, color.w), 0.01)
    collectgarbage("collect")
end

exports.TextAnim1 = TextAnim1
return exports
