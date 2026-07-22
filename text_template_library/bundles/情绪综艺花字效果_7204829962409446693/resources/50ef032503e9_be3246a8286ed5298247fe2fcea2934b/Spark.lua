local exports = exports or {}
local Spark = Spark or {}
Spark.__index = Spark
function Spark.new(construct, ...)
    local self = setmetatable({}, Spark)
    self.text = nil
    self.tween = nil
    self.tween1 = nil
    self.duration = 0
    if construct and Spark.constructor then Spark.constructor(self, ...) end
    return self
end

function Spark:constructor()

end

function Spark:onStart(comp)
    local sprite = comp.entity:getComponent("Sprite2DRenderer")
    self.text = comp.entity:getComponent("SDFText")

    if sprite ~= nil then
        local material = sprite.material
        self.tween = comp.entity.scene.tween:fromTo(material, 
                                                    {["_alpha"] = 0.0}, 
                                                    {["_alpha"] = 1.0}, 
                                                    0.1, 
                                                    Amaz.Ease.quadOut, 
                                                    nil, 
                                                    0.0, 
                                                    nil, 
                                                    false)
        self.tween1 = comp.entity.scene.tween:fromTo(material, 
                                                    {["_alpha"] = 1.0}, 
                                                    {["_alpha"] = 0.0}, 
                                                    0.1, 
                                                    Amaz.Ease.quadIn, 
                                                    nil, 
                                                    0.0, 
                                                    nil, 
                                                    false)
    end

    if self.text ~= nil then
        self.tween = comp.entity.scene.tween:fromTo(self.text, 
                                                    {["alpha"] = 0.0}, 
                                                    {["alpha"] = 1.0}, 
                                                    0.1, 
                                                    Amaz.Ease.quadOut, 
                                                    nil, 
                                                    0.0, 
                                                    nil, 
                                                    false)
        self.tween1 = comp.entity.scene.tween:fromTo(self.text, 
                                                    {["alpha"] = 1.0}, 
                                                    {["alpha"] = 0.0}, 
                                                    0.1, 
                                                    Amaz.Ease.quadIn, 
                                                    nil, 
                                                    0.0, 
                                                    nil, 
                                                    false)
    end
end

function Spark:seek(time)
    time = time % self.duration
    if(time <= self.tween.duration) then
        self.tween:set(time)
    else
        self.tween1:set(time - self.tween.duration)
    end
end

function Spark:setDuration(duration)
    self.duration = duration
    self.tween.duration = duration / 2.0
    self.tween1.duration = duration - self.tween.duration
end

function Spark:clear()
    if self.tween then
        self.tween:clear()
        self.tween = nil
    end
    if self.tween1 then
        self.tween1:set(0)
        self.tween1:clear()
        self.tween1 = nil
    end
end
exports.Spark = Spark
return exports
