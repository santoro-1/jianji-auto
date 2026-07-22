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
    self.shape = comp.entity:getComponent("IFShape")

    if self.shape ~= nil then
        self.tween = comp.entity.scene.tween:fromTo(self.shape, {["shapeGlobalAlpha"] = 0.0}, {["shapeGlobalAlpha"] = 1.0}, 0.1, Amaz.Ease.quadOut, nil, 0.0, nil, false)
        self.tween1 = comp.entity.scene.tween:fromTo(self.shape, {["shapeGlobalAlpha"] = 1.0}, {["shapeGlobalAlpha"] = 0.0}, 0.1, Amaz.Ease.quadIn, nil, 0.0, nil, false)
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
    if self.shape ~= nil then
        self.shape.shapeGlobalAlpha = 1.0
    end

    if self.tween then
        self.tween:set(0)
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
