local exports = exports or {}
local Transform = Transform or {}
Transform.__index = Transform
function Transform.new(construct, ...)
	local self = setmetatable({}, Transform)
	self.text = nil
	self.duration = 3.0
    self.speed = 2
	self.radius = 100
	self.charNum = 8
	self.scale = 1.0
	self.lastCount = 1
    if construct and Transform.constructor then Transform.constructor(self, ...) end
    return self
end

function Transform:constructor()

end
local pr = function(tag, message)
	Amaz.LOGI(tag, message)
end

local function remap(smin, smax, dmin, dmax, value)
	return (value - smin) / (smax - smin) * (dmax - dmin) + dmin
end
local remap01 = function(s, t, x)
	return (t - s) * x + s
end
local easeOutCubic = function(x)
	return 1 - math.pow(1 - x, 1)
end

local function clamp(min, max, value)
	return math.min(math.max(value, min), max)
end

local funcPosx = function(x)
	if x <= 0.55 then
		return math.pow((1/0.55)*x, 0.5)
	else
		return math.pow((1/0.55)*x, 0.3)
	end
end

local funcPosy = function(x)
	return math.pow(x, 2.0)
end


local getValue = function(propList, progress)
	local p = propList.func(remap(propList[1], propList[2], 0, 1,progress))
	return remap(0, 1, propList[3], propList[4], p)
end
function Transform:onStart(comp) 
	self.text = comp.entity:getComponent("SDFText")
	if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
	end

	self.trans = comp.entity:getComponent("Transform")
	self.midX = self.text.rect.x + self.text.rect.width * 0.5
	self.midY = self.text.rect.y + self.text.rect.height * 0.5
end


function Transform:seek(time)
	local curTime = time / self.duration
	local chars = self.text.chars
	local lineCount = 1
	local lineGap
	local wordGap
	if self.text.wordGap < 0 then
		wordGap = self.text.wordGap * 0.5
		lineGap = self.text.lineGap * 35
	else
		wordGap = self.text.wordGap * 0.2
		lineGap = self.text.lineGap * 20
	end
	local t1 = {}
	for i = 1, chars:size() do
		local char = chars:get(i-1)
		if char.utf8code == "\n" then
			lineCount = lineCount + 1
		else
			if t1[lineCount] == nil then
				t1[lineCount] = {}
			end
			table.insert(t1[lineCount], char)
		end
	end

	for k,lines in pairs(t1) do 
		local num = 8 + (k-1)*8
		local dis = 1
		if #lines <= num then
			self.charNum = 8 + (k-1)*8
			self.scale = math.max(0.98 - (k-1)*0.05 - wordGap,0.0)
		else
			self.charNum = #lines
			self.scale = math.max(1.0 - (1-1/math.pow((0.05*(#lines - num))+1,2)) - wordGap,0.0)
		end
		if k % 2 ~= 0 then
			dis = 1
		else
			dis = -1
		end 
		for i = 1, #lines do
			-- TODO to char
			local char = lines[i]
			local rotate = ((#lines - i+1) * (360/self.charNum)-90) 
			rotate = rotate + dis * (self.speed * curTime)*180/3.14
			local angle = ((#lines - i+1) * (360/self.charNum))*3.14/180
			
			angle = angle + dis * self.speed * curTime
			local  posX = math.cos(angle)*(self.radius+(60+lineGap)*(k-1)) + self.midX
			local  posY = math.sin(angle)*(self.radius+(60+lineGap)*(k-1)) + self.midY
			char.rotate = Amaz.Vector3f(0.0,0.0,rotate)
			char.position = Amaz.Vector3f(posX, posY,0.0)
			char.scale = Amaz.Vector3f(self.scale, self.scale, 1)
		end
	end
end


function Transform:resetData( ... )
	if self.text ~= nil then
    	local chars = self.text.chars 
		for i = 1, self.text.chars:size() do
			local char = chars:get(i - 1)
			if char.rowth ~= -1 then
				char.position = char.initialPosition
				char.rotate = Amaz.Vector3f(0, 0, 0)
				char.scale = Amaz.Vector3f(1, 1, 1)
				char.color = Amaz.Vector4f(1, 1, 1, 1)
			end
		end
		self.text.chars = chars
	end

	self.trans.localPosition = Amaz.Vector3f(0, 0, 0)
	self.trans.localEulerAngle = Amaz.Vector3f(0, 0, 0)
	self.trans.localScale = Amaz.Vector3f(1, 1, 1)
end

function Transform:setDuration(duration)
   self.duration = duration
end
function Transform:onLeave()
	self:resetData()
	if not self.first then
		self.text.renderToRT = false
	end
	self.first = true
end
function Transform:clear()
	self:resetData()
	if not self.first then
		self.text.renderToRT = false
	end
end

function Transform:onEnter()
    self.first = true
end

exports.Transform = Transform
return exports
