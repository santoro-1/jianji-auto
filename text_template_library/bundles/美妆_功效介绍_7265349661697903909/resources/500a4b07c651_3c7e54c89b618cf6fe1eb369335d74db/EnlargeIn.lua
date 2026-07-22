local exports = exports or {}
local EnlargeIn = EnlargeIn or {}
EnlargeIn.__index = EnlargeIn
function EnlargeIn.new(construct, ...)
    local self = setmetatable({}, EnlargeIn)
    self.text = nil
    self.tween = nil
    self.tween1 = nil
    if construct and EnlargeIn.constructor then EnlargeIn.constructor(self, ...) end
    return self
end

function EnlargeIn:constructor()

end

function EnlargeIn:onStart(comp)
    local sprite = comp.entity:getComponent("Sprite2DRenderer")
    self.text = comp.entity:getComponent("SDFText")

    if sprite ~= nil then
        local material = sprite.material
        self.tween = comp.entity.scene.tween:fromTo(material, {["_alpha"] = 0.0}, {["_alpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    if self.text ~= nil then
        self.tween = comp.entity.scene.tween:fromTo(self.text, {["alpha"] = 0.0}, {["alpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
    end

    local transform = comp.entity:getComponent("Transform")
    self.tween1 = comp.entity.scene.tween:fromTo(transform, {["localScale"] = Amaz.Vector3f(0.5, 0.5, 0.5) }, {["localScale"] = Amaz.Vector3f(1.0, 1.0, 1.0) }, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
end

function EnlargeIn:seek(time)
    self.tween:set(time)
    self.tween1:set(time)
end

function EnlargeIn:setDuration(duration)
    self.tween.duration = duration
    self.tween1.duration = duration
end

function EnlargeIn:clear()
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
exports.EnlargeIn = EnlargeIn
return exports
