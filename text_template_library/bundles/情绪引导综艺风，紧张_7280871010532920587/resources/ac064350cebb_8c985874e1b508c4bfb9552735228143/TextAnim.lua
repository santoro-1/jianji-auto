local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.sharedMaterial = nil
	self.materials = nil
    self.renderer = nil
    self.isVertical = 0.0
    self.duration = 0
    self.first = true
    self.radius = 0.01
    self.speed = 30.0
    self.deltaTime = 0.0
    self.lastTime = 0.0
    if construct and TextAnim.constructor then TextAnim.constructor(self, ...) end
    return self
end

function TextAnim:constructor()

end

function TextAnim:onStart(comp) 
	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end
    self.renderer = comp.entity:getComponent("MeshRenderer")
    self.transform = comp.entity:getComponent("Transform")
    self.first = true
end

function TextAnim:initAnim()
    self.text.renderToRT = true
    
    local materials = Amaz.Vector()
    local InsMaterials = self.sharedMaterial:instantiate()
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials
end

function TextAnim:seek(time)
    if self.first then
        self:initAnim()
        self.first = false
    end
    
    self.text.renderToRT = true
    self.renderer.materials = self.materials
    
    if self.lastTime == 0.0 then
        self.lastTime = time
    end
    
    self.deltaTime = self.deltaTime + math.abs(time - self.lastTime)
    self.lastTime = time

    if self.deltaTime > self.duration / self.speed then
        self.deltaTime = 0.0
        local rand = math.random()
        local r = 2 * math.pi * rand
        local distance = self.radius * rand
        local inputW = Amaz.BuiltinObject:getInputTextureWidth()
        local inputH = Amaz.BuiltinObject:getInputTextureHeight()
        local x = distance * math.sin(r)*540/inputW
        local y = distance * math.cos(r)*540/inputH

        self.transform.localPosition = Amaz.Vector3f(x, y, 0)
    end
    
end
function TextAnim:resetData()
    if self.text ~= nil and not self.clearState then
        local chars = self.text.chars 
        for i = 1, chars:size() do
                local char = chars:get(i - 1)
                if char.rowth ~= -1 then
                        char.position = char.initialPosition
                        char.rotate = Amaz.Vector3f(0, 0, 0)
                        char.scale = Amaz.Vector3f(1, 1, 1)
                        char.color = Amaz.Vector4f(1, 1, 1, 1)
                end
        end
        self.clearState = true
        self.text.chars = chars
        self.text.renderToRT = false
        self.renderer.materials = Amaz.Vector()
    end

    self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
    self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
    self.trans.localScale = Amaz.Vector3f(1, 1, 1)
end
function TextAnim:setDuration(duration)
    self.duration = duration
end

function TextAnim:clear()
    self:resetData()
 
end

function TextAnim:onEnter()
	self.first = true
	self.clearState = false
	-- self.text.renderToRT = true
end


function TextAnim:onLeave()
    self:resetData()
    self.first = true
end
exports.TextAnim = TextAnim
return exports
