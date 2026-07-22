local exports = exports or {}
local TextWave = TextWave or {}
TextWave.__index = TextWave
function TextWave.new(construct, ...)
    local self = setmetatable({}, TextWave)
    self.duration = 0.3
    self.height = 24
    -- print("New")
    if construct and TextWave.constructor then TextWave.constructor(self, ...) end
    return self
end

function TextWave:constructor()

end

function TextWave:onStart(comp) 

	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end

	local animTrans = comp.entity:getComponent("Transform")
    local parentTrans = animTrans.parent

    local userS = parentTrans.localScale
    local userR = parentTrans.localOrientation
    local userT = parentTrans.localPosition
    local animS = animTrans.localScale
    local animR = animTrans.localOrientation
	local animT = animTrans.localPosition

	animTrans.localScale = Amaz.Vector3f(1,1,1);
	animTrans.localPosition = Amaz.Vector3f(0,0,0);
end

function TextWave:seek(time)
	time = time % self.duration
	local t = time / self.duration
	local text = self.text
	local chars = text.chars
	local count = chars:size()

	local theta = math.floor(t + 0.5) * 5;
	for i = 0, count - 1 do
		local char = chars:get(i);
		local offset = (2 * (i % 2) - 1) * theta;
		char.rotate = Amaz.Vector3f(0, 0, offset);
	end
    self.text.chars = chars
end

function TextWave:setDuration(duration)
   self.duration = duration
end

function TextWave:ResetData()
	local text = self.text
	if text ~= nil then
		local chars = text.chars
		local count = chars:size()
		for i = 0, count - 1 do
			local char = chars:get(i)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
			end
		end
		self.text.chars = chars
	end
end

function TextWave:clear()
	self:ResetData()
end

function TextWave:onEnter()
end


function TextWave:onLeave()
	self:ResetData()
	-- self.tweenDirty = true
end
exports.TextWave = TextWave
return exports
