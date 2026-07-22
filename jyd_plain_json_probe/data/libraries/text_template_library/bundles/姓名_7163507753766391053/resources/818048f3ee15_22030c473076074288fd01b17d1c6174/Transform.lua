local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
    local self = setmetatable({}, Transform)
    self.tween = nil
    self.tween1 = nil
    self.comp = nil
    self.text = nil
    self.sprite = nil
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end

local function updateHandle(comp)
    if comp == nil then 
        return 
    end

    local animTrans = comp.entity:getComponent("Transform")
    local parentTrans = animTrans.parent
    
    local userS = parentTrans.localScale
    local userR = parentTrans.localOrientation
    local userT = parentTrans.localPosition

    local animS = animTrans.localScale
    local animR = animTrans.localOrientation
    local animT = animTrans.localPosition

    local mat = parentTrans.localMatrix
    
    -- move to (0,0)
    mat:AddTranslate(animT * userS.y)

    -- set anim local matrix
    local animLocal = parentTrans.localMatrix:Invert_Full() * mat
    animTrans.localMatrix = animLocal
end

function Transform:onStart(comp)
    self.comp = comp
    local textureH 
    local screenH = Amaz.BuiltinObject:getOutputTextureHeight()

    self.sprite = comp.entity:getComponent("Sprite2DRenderer")
    self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end

    if self.sprite ~= nil then
        local material = self.sprite.material
        textureH = self.sprite:getTextureSize().y
        self.tween = comp.entity.scene.tween:fromTo(material, {["_alpha"] = 0.0}, {["_alpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    if self.text ~= nil then
        textureH = self.text.rect.height
        self.tween = comp.entity.scene.tween:fromTo(self.text, {["alpha"] = 0.0}, {["alpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    local transform = comp.entity:getComponent("Transform")
    self.tween1 = comp.entity.scene.tween:fromTo(transform, {["localPosition"] = Amaz.Vector3f(0.0, -2.66 * textureH / screenH, 0.0) }, {["localPosition"] = Amaz.Vector3f(0.0, 0.0, 0.0) }, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
end

function Transform:seek(time)
    self.tween:set(time)
    self.tween1:set(time)
    updateHandle(self.comp)
end

function Transform:setDuration(duration)
    self.tween.duration = duration
    self.tween1.duration = duration
end

function Transform:clear()
    if self.tween then
        self.tween:set(self.tween.duration)
        self.tween:clear()
        self.tween = nil
    end
    if self.tween1 then
        self.tween1:set(self.tween1.duration)
        self.tween1:clear()
        self.tween1 = nil
    end
end
exports.Transform = Transform
return exports
