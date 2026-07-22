local exports = exports or {}
local TextAnim = TextAnim or {}
TextAnim.__index = TextAnim
function TextAnim.new(construct, ...)
    local self = setmetatable({}, TextAnim)
    self.sharedMaterial = nil
    self.tween = nil
	self.materials = nil
    self.renderer = nil
    self.duration = 0
    self.isInit = false
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
    self.props = self.renderer.props;
    self:seek(0)
end

function TextAnim:initAnim()
    if self.isInit == false then
        self.text.renderToRT = true
        local materials = Amaz.Vector()
        local InsMaterials = self.sharedMaterial:instantiate()
        materials:pushBack(InsMaterials)
        self.materials = materials
        self.renderer.materials = self.materials
        -- self.tween = self.text.entity.scene.tween:fromTo(self.materials:get(0), {["eraseUV"] = Amaz.Vector2f(1.4, 0)}, {["eraseUV"] = Amaz.Vector2f(0, 0)}, 0.4 * self.duration, Amaz.Ease.linear, nil, 0.6 * self.duration, nil, false)
        self.tween = self.text.entity.scene.tween:fromTo(self.materials:get(0), {["eraseUV"] = Amaz.Vector2f(0, 0)}, {["eraseUV"] = Amaz.Vector2f(1.4, 0)}, 0.4, Amaz.Ease.linear, nil, 0.6, nil, false)
        self.tween.duration = self.duration
        self.isInit = true;
    end
end

function TextAnim:seek(time)
    self:initAnim()
    if not self.leaveState then
        if time >= 0 then
            self.text.renderToRT = true
            self.renderer.materials = self.materials
        else
            self.text.renderToRT = false
        end
        self.tween:set(time)
    end
end

function TextAnim:setDuration(duration)
    self.duration = duration
    if self.tween then
        self.tween.duration = duration
    end
end

function TextAnim:clear()
	if self.tween then
        self.tween:clear()
        self.tween = nil
        self.text.renderToRT = false
        self.isInit = false
    end
end

function TextAnim:onEnter()
	self.isInit = false
    self.leaveState = false
end

function TextAnim:onLeave()
    if self.text ~= nil then
		self:clear()
	end
    self.leaveState = true
end

exports.TextAnim = TextAnim
return exports
