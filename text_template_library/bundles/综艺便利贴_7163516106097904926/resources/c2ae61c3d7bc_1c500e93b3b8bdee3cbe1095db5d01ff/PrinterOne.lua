local exports = exports or {}
local PrinterOne = PrinterOne or {}
PrinterOne.__index = PrinterOne
function PrinterOne.new(construct, ...)
    local self = setmetatable({}, PrinterOne)
    self.duration = 3.0
    self.count = 0
    self.tweens = {}
    -- print("New")
    if construct and PrinterOne.constructor then PrinterOne.constructor(self, ...) end
    return self
end

function PrinterOne:constructor()

end

local function linearFunc(t,ratio,init)
	return ratio*t+init
end

local function remap01(a, b, x)
    if x < a then return 0 end
    if x > b then return 1 end
    return (x - a) / (b - a)
end

local function mix(a, b, x)
    return a * (1 - x) + b * x
end

local function FloorEase(t, b, c, d)
	t=t/d
	if (t < 0.99999) then
		return b
	else
		return b + c
	end
end

local function Easing(t, b, c, d)
	t=t/d
	t=math.pow(t,4)
	return math.min(linearFunc(t,c,b), c)
end

local function getVersionNum(sdk_str)
	local sp_str = "."
	local splits = {}
	local sdk_version_num = 0
	if sdk_str and sdk_str ~= "" then
		-- normal split use gmatch
		local pattern = "[^" .. sp_str .. "]+"
		for str in string.gmatch(sdk_str, pattern) do
			table.insert(splits, str)
		end
	end
	local len = #splits
	local m_num = 10
	for i=len,1,-1 do
		sdk_version_num = sdk_version_num + tonumber(splits[i])*m_num
		m_num = m_num * 10
	end

	return sdk_version_num
end

local function isNotSupportVersion()
	return not (getVersionNum(EffectSdk.getSDKVersion()) >= getVersionNum("15.7.0"))
end

local function checkDirty(self)
	if self.tweenDirty then
		self.count = self.text.chars:size()
		self.tweens = {}
		for i = 1, self.count do
			local char = self.text.chars:get(i - 1)
			local duration = Amaz.Ease.linear(i / (self.count + 1), 0 , self.duration, 1)
			-- print(duration)
			table.insert(self.tweens, i, self.text.entity.scene.tween:fromTo(char, 
													{["color.w"] = 0},
													{["color.w"] = 1.0},
													duration,
													Amaz.Ease.Floor,
													nil,
													0.0,
													nil,
													false
													))
			self.tweenDirty = false
		end
	end
end

function PrinterOne:onStart(comp) 
	if isNotSupportVersion() then
		return
	end
	self.text = comp.entity:getComponent('SDFText')
    if self.text == nil then
        local text = comp.entity:getComponent('Text')
        if text ~= nil then
			self.text = comp.entity:addComponent('SDFText')
            self.text:setTextWrapper(text)
        end
    end

	self.richText = comp.entity:getComponent('Text')
	self.tweenDirty = true
	-- checkDirty(self)
	-- print("onStart")
end

function PrinterOne:seek(time)
	--print("Time:"..tostring(time))
	-- print(self.duration)
	if isNotSupportVersion() then
		return
	end
	if self.first == nil then
		if self.richText and self.richText.str then
			self.oriLetters = self.richText.letters:clone()
			self.oriStr = self.richText.str

			self.oriLetterAlphas = {}
			for i = 1, self.richText.letters:size() do
				local letter = self.richText.letters:get(i - 1)
				if letter.instanceColor then
					local color = letter.instanceColor
					table.insert(self.oriLetterAlphas, color.a)
				end
			end

		end
		self.first = true
	end

	if self.richText and self.richText.str then
		for i = 1, self.richText.letters:size() do
			local letter = self.richText.letters:get(i - 1)
			local oriColorAlpha = self.oriLetterAlphas[i]
			local color = letter.instanceColor

			local duration = Amaz.Ease.linear(i / (self.richText.letters:size() + 1), 0 , self.duration, 1)
			-- local p = remap01(0, duration, time)
			local p = Easing(time, 0, 1, duration)
			letter.instanceColor = Amaz.Color(
				color.r,
				color.g,
				color.b,
				oriColorAlpha * p
			)
		end
	end

	
    -- checkDirty(self)
    -- for key, value in pairs(self.tweens) do
    -- 	value:set(time)
    -- end
    -- local chars = self.text.chars 
    -- self.text.chars= chars
end

function PrinterOne:setDuration(duration)
	if isNotSupportVersion() then
		return
	end
   self.duration = duration
   self.tweenDirty = true
end


function PrinterOne:onLeave()
	if isNotSupportVersion() then
		return
	end
	for key, value in pairs(self.tweens) do
    	value:set(self.duration)
        value:clear()
    end
	self.tweens = {}
	self.tweenDirty = true
	if self.richText and self.richText.str then
		self.richText.str = self.oriStr
		self.richText.letters = self.oriLetters
	end
	self.first = nil
end

function PrinterOne:clear()
	--print("Clear")
	if isNotSupportVersion() then
		return
	end
	self.tweenDirty = true
	for key, value in pairs(self.tweens) do
    	value:set(self.duration)
        value:clear()
    end 
    self.tweens = {}
    -- if self.text ~= nil then
    -- 	local chars = self.text.chars 
   	-- 	self.text.chars= chars
   	-- end

	if self.richText and self.richText.str then
		self.richText.str = self.oriStr
		self.richText.letters = self.oriLetters
	end
	self.first = nil
end

exports.PrinterOne = PrinterOne
return exports
