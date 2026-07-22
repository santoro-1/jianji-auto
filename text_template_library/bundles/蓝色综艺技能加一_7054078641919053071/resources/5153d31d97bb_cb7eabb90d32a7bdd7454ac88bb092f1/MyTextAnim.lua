local exports = exports or {}
local MyTextAnim = {}
MyTextAnim.__index = MyTextAnim

function MyTextAnim.new(construct, ...)
    local self = setmetatable({}, MyTextAnim)
    self.sharedMaterial1 = nil
    self.duration = 3.0
    self.appearDur = 0.0
    self.maxYOffset = 0.4
    self.offset = 0.0
    self.materials = nil
    if construct and MyTextAnim.constructor then
        MyTextAnim.constructor(self, ...)
    end
    return self
end

function MyTextAnim:constructor()

end

function MyTextAnim:onStart(comp)
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
        -- self.text.targetRTExtraSize = Amaz.Vector2f(0.0, self.text.rect.height * 2.50)
        self.text.verticalPadding = 2.5
    else
        self.renderer = comp.entity:getComponent("Sprite2DRenderer")
    end
    self.first = true
end



function MyTextAnim:setOffsetAndAlpha(time, offsetName, alphaName)
    local yOffset = 0
    local alpha = 1
    if (time <= self.appearDur) then
        yOffset = 0.0
        alpha = time / self.appearDur
    else
        local pct = (time - self.appearDur) / (self.duration - self.appearDur)
        yOffset = pct * self.maxYOffset
        alpha = (1.0 - pct)
    end
    local mat = self.materials:get(0)
    mat:setFloat(offsetName, yOffset)
    mat:setFloat(alphaName, alpha)
end

function MyTextAnim:initAnim()
    self.text.renderToRT = true
    local materials = Amaz.Vector()
    local InsMaterials = self.sharedMaterial1:instantiate()
    materials:pushBack(InsMaterials)
    self.materials = materials
    self.renderer.materials = self.materials
end

function MyTextAnim:seek(time)
    if self.first then
        self:initAnim()
        self.first = false
        if self.text ~= nil then
            self.text.verticalPadding = 2.5
        end
    end

    local duration = self.duration
    self:setOffsetAndAlpha(time % duration, "u_yOffset", "u_alpha")
    self:setOffsetAndAlpha((time + self.offset) % duration, "u_yOffset1", "u_alpha1")
    self:setOffsetAndAlpha((time + self.offset * 2.0) % duration, "u_yOffset2", "u_alpha2")
end

function MyTextAnim:setDuration(duration)
    self.duration = duration
    self.offset = self.duration / 3
    self.appearDur = self.offset
end

function MyTextAnim:clear()
	if self.text ~= nil and not self.clearState then
		for i = 1, self.text.chars:size() do
			local char = self.text.chars:get(i - 1)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
				char.color = Amaz.Vector4f(1, 1, 1, 1)
			end
		end
    	local chars = self.text.chars
		self.text.chars= chars
        self.text.renderToRT = false
        self.clearState = true
        self.text.verticalPadding = 0
    end
    -- self.renderer.sharedMaterials = Amaz.Vector()
    -- self.renderer.materials = Amaz.Vector()
end


function MyTextAnim:onEnter()
    self.first = true
    self.clearState = false
end

function MyTextAnim:onLeave()
	if self.text ~= nil and not self.clearState then
		self:clear()
	end
    self.first = true
end

exports.MyTextAnim = MyTextAnim

return exports
