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
    self.first = true
end

function TextAnim:initAnim()
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    materials:pushBack(self.sharedMaterial)
    self.renderer.sharedMaterials = materials
    self.materials = self.renderer.materials
end

function TextAnim:seek(time)
    if self.first then
        self:initAnim()
        self.first = false
    end
    
    self.text.renderToRT = true
    self.renderer.materials = self.materials
    
    time = time % self.duration
    time = time / self.duration
    
    if self.text.typeSettingKind == Amaz.TypeSettingKind.VERTICAL then
        self.isVertical = 1
    else
        self.isVertical = 0
    end
    if self.text.chars:size() ~= 0 then
        local altitude = 0.2 * self.text.chars:get(0).height;  -- 振幅（altitude单位：像素）
        local extraH = altitude * 2.0
        self.text.targetRTExtraSize = Amaz.Vector2f(0, extraH)
        self.materials:get(0):setVec3("param", Amaz.Vector3f(self.isVertical, time, altitude / (self.text.rect.height + extraH)))
    else
        self.text.targetRTExtraSize = Amaz.Vector2f(0, 0)
        self.materials:get(0):setVec3("param", Amaz.Vector3f(self.isVertical, time, 0))
    end
end

function TextAnim:setDuration(duration)
    self.duration = duration
end
function TextAnim:resetData()
    if not self.first then
        self.renderer.sharedMaterials = Amaz.Vector()
        self.text.renderToRT = false
    end
end
function TextAnim:clear()
    -- print("clear")
    self:resetData()
end

function TextAnim:onEnter()
	self.first = true
	-- self.clearState = false
	-- self.text.renderToRT = true
end


function TextAnim:onLeave()
    self:resetData()
    self.first = true
end

exports.TextAnim = TextAnim
return exports
